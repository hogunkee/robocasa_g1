import argparse
import cv2
import datetime
import json
import os
import hashlib
import random
import shutil
import sys
import time

import h5py
import imageio
import numpy as np
import robocasa
import robosuite
import robosuite.utils.transform_utils as T
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from itertools import product
from termcolor import colored
from tqdm import tqdm


def playback_trajectory_with_env(
    args,
    f,
    ep,
    env,
    initial_state,
    states,
    actions=None,
    render=False,
    video_writer=None,
    video_skip=5,
    camera_names=None,
    first=False,
    verbose=False,
):
    """
    Helper function to playback a single trajectory using the simulator environment.
    If @actions are not None, it will play them open-loop after loading the initial state.
    Otherwise, @states are loaded one by one.

    Args:
        args (argparse.Namespace): command line arguments
        f (hdf5 file): hdf5 file object
        ep (str): episode name
        env (instance of EnvBase): environment
        initial_state (dict): initial simulation state to load
        states (np.array): array of simulation states to load
        actions (np.array): if provided, play actions back open-loop instead of using @states
        render (bool): if True, render on-screen
        video_writer (imageio writer): video writer
        video_skip (int): determines rate at which environment frames are written to video
        camera_names (list): determines which camera(s) are used for rendering. Pass more than
            one to output a video with multiple camera views concatenated horizontally.
        first (bool): if True, only use the first frame of each episode.
        verbose (bool): if True, print additional information
    """
    write_video = video_writer is not None
    video_count = 0
    assert not (render and write_video)

    # load the initial state
    ## this reset call doesn't seem necessary.
    ## seems ok to remove but haven't fully tested it.
    ## removing for now
    # env.reset()

    if verbose:
        ep_meta = json.loads(initial_state["ep_meta"])
        lang = ep_meta.get("lang", None)
        if lang is not None:
            print(colored(f"Instruction: {lang}", "green"))
        print(colored("Spawning environment...", "yellow"))
    reset_to(env, initial_state)

    traj_len = states.shape[0]
    action_playback = actions is not None
    if action_playback:
        assert states.shape[0] == actions.shape[0]

    if render is False:
        print(colored("Running episode...", "yellow"))

    if args.num_frames is None:
        start_frame = 0
        end_frame = traj_len
    else:
        start_frame = random.randrange(traj_len - min(args.num_frames, traj_len) + 1)
        end_frame = start_frame + min(args.num_frames, traj_len)
    for i in tqdm(range(start_frame, end_frame)):
        start = time.time()

        if action_playback:
            env.step(actions[i])
            if i < traj_len - 1:
                # check whether the actions deterministically lead to the same recorded states
                state_playback = np.array(env.sim.get_state().flatten())
                if not np.all(np.equal(states[i + 1], state_playback)):
                    err = np.linalg.norm(states[i + 1] - state_playback)
                    if verbose or i == traj_len - 2:
                        print(
                            colored(
                                "warning: playback diverged by {} at step {}".format(
                                    err, i
                                ),
                                "yellow",
                            )
                        )
        else:
            reset_to(env, {"states": states[i]})

        # on-screen render
        if render:
            if env.viewer is None:
                env.initialize_renderer()

            # so that mujoco viewer renders
            env.viewer.update()

            max_fr = 60
            elapsed = time.time() - start
            diff = 1 / max_fr - elapsed
            if diff > 0:
                time.sleep(diff)

        # video render
        if write_video:
            if video_count % video_skip == 0:
                video_img = []
                for cam_name in camera_names:
                    im = env.sim.render(
                        height=args.render_height,
                        width=args.render_width,
                        camera_name=cam_name,
                    )[::-1]
                    video_img.append(im)
                video_img = np.concatenate(
                    video_img, axis=1
                )  # concatenate horizontally
                video_writer.append_data(video_img)
            video_count += 1

        if first:
            break

    if render:
        env.viewer.close()
        env.viewer = None


def playback_trajectory_with_obs(
    traj_grp,
    video_writer,
    video_skip=5,
    image_names=None,
    first=False,
):
    """
    This function reads all "rgb" observations in the dataset trajectory and
    writes them into a video.

    Args:
        traj_grp (hdf5 file group): hdf5 group which corresponds to the dataset trajectory to playback
        video_writer (imageio writer): video writer
        video_skip (int): determines rate at which environment frames are written to video
        image_names (list): determines which image observations are used for rendering. Pass more than
            one to output a video with multiple image observations concatenated horizontally.
        first (bool): if True, only use the first frame of each episode.
    """
    assert (
        image_names is not None
    ), "error: must specify at least one image observation to use in @image_names"
    video_count = 0

    traj_len = traj_grp["obs/{}".format(image_names[0] + "_image")].shape[0]
    for i in range(traj_len):
        if video_count % video_skip == 0:
            # concatenate image obs together
            im = [traj_grp["obs/{}".format(k + "_image")][i] for k in image_names]
            frame = np.concatenate(im, axis=1)
            video_writer.append_data(frame)
        video_count += 1

        if first:
            break


def get_env_metadata_from_dataset(dataset_path, ds_format="robomimic"):
    """
    Retrieves env metadata from dataset.

    Args:
        dataset_path (str): path to dataset

    Returns:
        env_meta (dict): environment metadata. Contains 3 keys:

            :`'env_name'`: name of environment
            :`'type'`: type of environment, should be a value in EB.EnvType
            :`'env_kwargs'`: dictionary of keyword arguments to pass to environment constructor
    """
    dataset_path = os.path.expanduser(dataset_path)
    try:
        f = h5py.File(dataset_path, "r")
    except Exception as e:
        print(f"Error opening file {args.dataset}: {e}")
        sys.exit(1)
    if ds_format == "robomimic":
        env_meta = json.loads(f["data"].attrs["env_args"])
    else:
        raise ValueError
    f.close()
    return env_meta


class ObservationKeyToModalityDict(dict):
    """
    Custom dictionary class with the sole additional purpose of automatically registering new "keys" at runtime
    without breaking. This is mainly for backwards compatibility, where certain keys such as "latent", "actions", etc.
    are used automatically by certain models (e.g.: VAEs) but were never specified by the user externally in their
    config. Thus, this dictionary will automatically handle those keys by implicitly associating them with the low_dim
    modality.
    """

    def __getitem__(self, item):
        # If a key doesn't already exist, warn the user and add default mapping
        if item not in self.keys():
            print(
                f"ObservationKeyToModalityDict: {item} not found,"
                f" adding {item} to mapping with assumed low_dim modality!"
            )
            self.__setitem__(item, "low_dim")
        return super(ObservationKeyToModalityDict, self).__getitem__(item)


def reset_to(env, state):
    """
    Reset to a specific simulator state.

    Args:
        state (dict): current simulator state that contains one or more of:
            - states (np.ndarray): initial state of the mujoco environment
            - model (str): mujoco scene xml

    Returns:
        observation (dict): observation dictionary after setting the simulator state (only
            if "states" is in @state)
    """
    should_ret = False
    if "model" in state:
        if state.get("ep_meta", None) is not None:
            # set relevant episode information
            ep_meta = json.loads(state["ep_meta"])
        else:
            ep_meta = {}
        if hasattr(env, "set_attrs_from_ep_meta"):  # older versions had this function
            env.set_attrs_from_ep_meta(ep_meta)
        elif hasattr(env, "set_ep_meta"):  # newer versions
            env.set_ep_meta(ep_meta)
        # this reset is necessary.
        # while the call to env.reset_from_xml_string does call reset,
        # that is only a "soft" reset that doesn't actually reload the model.
        env.reset()
        robosuite_version_id = int(robosuite.__version__.split(".")[1])
        if robosuite_version_id <= 3:
            from robosuite.utils.mjcf_utils import postprocess_model_xml

            xml = postprocess_model_xml(state["model"])
        else:
            # v1.4 and above use the class-based edit_model_xml function
            xml = env.edit_model_xml(state["model"])

        env.reset_from_xml_string(xml)
        env.sim.reset()
        # hide teleop visualization after restoring from model
        # env.sim.model.site_rgba[env.eef_site_id] = np.array([0., 0., 0., 0.])
        # env.sim.model.site_rgba[env.eef_cylinder_id] = np.array([0., 0., 0., 0.])
    if "states" in state:
        env.sim.set_state_from_flattened(state["states"])
        env.sim.forward()
        should_ret = True

    # update state as needed
    if hasattr(env, "update_sites"):
        # older versions of environment had update_sites function
        env.update_sites()
    if hasattr(env, "update_state"):
        # later versions renamed this to update_state
        env.update_state()

    # if should_ret:
    #     # only return obs if we've done a forward call - otherwise the observations will be garbage
    #     return get_observation()
    return None


def make_env_from_args(args):
    # # need to make sure ObsUtils knows which observations are images, but it doesn't matter
    # # for playback since observations are unused. Pass a dummy spec here.
    # dummy_spec = dict(
    #     obs=dict(
    #             low_dim=["robot0_eef_pos"],
    #             rgb=[],
    #         ),
    # )
    # initialize_obs_utils_with_obs_specs(obs_modality_specs=dummy_spec)

    env_meta = get_env_metadata_from_dataset(dataset_path=args.dataset)
    if args.use_abs_actions:
        env_meta["env_kwargs"]["controller_configs"][
            "control_delta"
        ] = False  # absolute action space

    env_kwargs = env_meta["env_kwargs"]
    env_kwargs["env_name"] = env_meta["env_name"]
    env_kwargs["has_renderer"] = False
    env_kwargs["renderer"] = "mjviewer"
    env_kwargs["has_offscreen_renderer"] = not args.render
    env_kwargs["use_camera_obs"] = False

    if args.verbose:
        print(
            colored(
                "Initializing environment for {}...".format(env_kwargs["env_name"]),
                "yellow",
            )
        )
    if "env_lang" in env_kwargs:
        env_kwargs.pop("env_lang")
    env = robosuite.make(**env_kwargs)
    return env


# Three components when processing a demo:
# 1. Load the dataset into the variable `f`: This step ensures that the necessary data for the demo,
#    such as states, actions, and metadata, is available for playback.
# 2. Initialize a video writer: If video output is required, this step sets up the writer to save
#    the playback as a video file.
# 3. Create the environment `env` (optional): This step initializes the simulation environment, which
#    is essential for rendering and interacting with the demo data.
def process_demo(args, ep):
    print(colored("\nPlaying back episode: {}".format(ep), "yellow"))

    # maybe dump video
    write_video = args.render is not True
    video_writer = None
    if write_video:
        ep_path = args.video_path[:-4] + "_" + ep + ".mp4"
        video_writer = imageio.get_writer(ep_path, fps=20)

    try:
        f = h5py.File(args.dataset, "r")
    except Exception as e:
        print(f"Error opening file {args.dataset}: {e}")
        sys.exit(1)

    if args.use_obs:
        playback_trajectory_with_obs(
            traj_grp=f["data/{}".format(ep)],
            video_writer=video_writer,
            video_skip=args.video_skip,
            image_names=args.render_image_names,
            first=args.first,
        )
        if write_video:
            print(colored(f"Saved video to {ep_path}", "green"))
            video_writer.close()
        f.close()
        return

    # create environment only if not playing back with observations
    env = make_env_from_args(args)

    def make_ik_indicator_invisible(str_xml):
        import xml.etree.ElementTree as ET

        raw_xml = ET.fromstring(str_xml)
        for site in raw_xml.findall(".//site"):
            name = site.get("name", "")
            if "pinch_spheres" in name:
                print(
                    colored(
                        "make site invisible: {}".format(name),
                        "yellow",
                    )
                )
                site.set("rgba", "0 0 0 0")
        return ET.tostring(raw_xml)

    # prepare initial state to reload from
    states = f["data/{}/states".format(ep)][()]
    initial_state = dict(states=states[0])
    initial_state["model"] = make_ik_indicator_invisible(
        f["data/{}".format(ep)].attrs["model_file"]
    )
    if args.use_current_env_model:
        initial_state["model"] = env.sim.model.get_xml()
    initial_state["ep_meta"] = f["data/{}".format(ep)].attrs.get("ep_meta", None)

    if args.extend_states:
        states = np.concatenate((states, [states[-1]] * 50))

    # supply actions if using open-loop action playback
    actions = None
    assert not (
        args.use_actions and args.use_abs_actions
    )  # cannot use both relative and absolute actions
    if args.use_actions:
        actions = f["data/{}/actions".format(ep)][()]
    elif args.use_abs_actions:
        actions = f["data/{}/actions_abs".format(ep)][()]  # absolute actions

    playback_trajectory_with_env(
        args=args,
        f=f,
        ep=ep,
        env=env,
        initial_state=initial_state,
        states=states,
        actions=actions,
        render=args.render,
        video_writer=video_writer,
        video_skip=args.video_skip,
        camera_names=args.render_image_names,
        first=args.first,
        verbose=args.verbose,
    )

    if write_video:
        print(colored(f"Saved video to {ep_path}", "green"))
        video_writer.close()

    f.close()
    env.close()


def playback_dataset(args):
    # some arg checking
    write_video = args.render is not True
    if args.video_path is None:
        args.video_path = args.dataset.split(".hdf5")[0] + ".mp4"
        if args.use_actions:
            args.video_path = args.dataset.split(".hdf5")[0] + "_use_actions.mp4"
        elif args.use_abs_actions:
            args.video_path = args.dataset.split(".hdf5")[0] + "_use_abs_actions.mp4"
    assert not (args.render and write_video)  # either on-screen or video but not both

    # Auto-fill camera rendering info if not specified
    if args.render_image_names is None:
        # We fill in the automatic values
        env_meta = get_env_metadata_from_dataset(dataset_path=args.dataset)
        args.render_image_names = "robot0_agentview_center"

    if args.render:
        # on-screen rendering can only support one camera
        assert len(args.render_image_names) == 1

    if args.use_obs:
        assert write_video, "playback with observations can only write to video"
        assert (
            not args.use_actions and not args.use_abs_actions
        ), "playback with observations is offline and does not support action playback"

    try:
        f = h5py.File(args.dataset, "r")
    except Exception as e:
        print(f"Error opening file {args.dataset}: {e}")
        sys.exit(1)

    # list of all demonstration episodes (sorted in increasing number order)
    if args.filter_key is not None:
        print("using filter key: {}".format(args.filter_key))
        demos = [
            elem.decode("utf-8")
            for elem in np.array(f["mask/{}".format(args.filter_key)])
        ]
    elif "data" in f.keys():
        demos = list(f["data"].keys())

    inds = np.argsort([int(elem[5:]) for elem in demos])
    demos = [demos[i] for i in inds]

    # maybe reduce the number of demonstrations to playback
    if args.n is not None:
        random.shuffle(demos)
        demos = demos[: args.n]

    if args.num_parallel_jobs == 1:
        # reuse the same environment for all demos
        for ep in tqdm(demos):
            process_demo(args, ep)
    else:
        with ProcessPoolExecutor(max_workers=args.num_parallel_jobs) as executor:
            process_demo_with_args = partial(process_demo, args)
            futures = {executor.submit(process_demo_with_args, ep): ep for ep in demos}
            for future in tqdm(as_completed(futures), total=len(futures)):
                ep = futures[future]
                try:
                    result = (
                        future.result()
                    )  # Raises any exception that occurred during execution
                except Exception as e:
                    print(f"[ERROR] Episode {ep}: {e}")

    f.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=str,
        help="path to hdf5 dataset",
    )
    parser.add_argument(
        "--filter_key",
        type=str,
        default=None,
        help="(optional) filter key, to select a subset of trajectories in the file",
    )

    # number of trajectories to playback. If omitted, playback all of them.
    parser.add_argument(
        "--n",
        type=int,
        default=None,
        help="(optional) stop after n trajectories are played",
    )

    parser.add_argument(
        "--num_parallel_jobs",
        type=int,
        default=1,
        help="(optional) number of parallel jobs to use for playback",
    )

    parser.add_argument(
        "--num_frames",
        type=int,
        default=None,
        help="(optional) number of frames to playback",
    )

    # Use image observations instead of doing playback using the simulator env.
    parser.add_argument(
        "--use-obs",
        action="store_true",
        help="visualize trajectories with dataset image observations instead of simulator",
    )

    # Playback stored dataset actions open-loop instead of loading from simulation states.
    parser.add_argument(
        "--use-actions",
        action="store_true",
        help="use open-loop action playback instead of loading sim states",
    )

    # Playback stored dataset absolute actions open-loop instead of loading from simulation states.
    parser.add_argument(
        "--use-abs-actions",
        action="store_true",
        help="use open-loop action playback with absolute position actions instead of loading sim states",
    )

    # Whether to render playback to screen
    parser.add_argument(
        "--render",
        action="store_true",
        help="on-screen rendering",
    )

    # Dump a video of the dataset playback to the specified path
    parser.add_argument(
        "--video_path",
        type=str,
        default=None,
        help="(optional) render trajectories to this video file path",
    )

    # How often to write video frames during the playback
    parser.add_argument(
        "--video_skip",
        type=int,
        default=1,
        help="render frames to video every n steps",
    )

    # camera names to render, or image observations to use for writing to video
    parser.add_argument(
        "--render_image_names",
        type=str,
        nargs="+",
        default=[
            "egoview",
        ],
        help="(optional) camera name(s) / image observation(s) to use for rendering on-screen or to video. Default is"
        "None, which corresponds to a predefined camera for each env type",
    )

    parser.add_argument(
        "--render_height",
        type=int,
        default=512,
        help="(optional) height of rendered video frames",
    )

    parser.add_argument(
        "--render_width",
        type=int,
        default=512,
        help="(optional) width of rendered video frames",
    )

    # Only use the first frame of each episode
    parser.add_argument(
        "--first",
        action="store_true",
        help="use first frame of each episode",
    )

    parser.add_argument(
        "--extend_states",
        action="store_true",
        help="play last step of episodes for 50 extra frames",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="log additional information",
    )

    parser.add_argument(
        "--use_current_env_model",
        action="store_true",
        help="use the current environment model instead of the one stored in the dataset",
    )

    args = parser.parse_args()
    playback_dataset(args)
