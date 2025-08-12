# Robocasa-G1

**Robocasa-G1** is built upon the [Robocasa](https://github.com/robocasa/robocasa) and [RoboCasa GR-1 Tabletop Tasks](https://github.com/robocasa/robocasa-gr1-tabletop-tasks) simulation frameworks.
This repository is a fork that adds support for the **Unitree G1 humanoid robot**.
It integrates the G1 model, assets, and control interface into Robocasa’s household manipulation environments, enabling tabletop tasks specifically tailored to G1’s kinematics and workspace.

---

## Overview

Robocasa-G1 enables:
- Simulation of Unitree G1 in Robocasa environments
- Tabletop task setups adapted for G1 reach and joint limits
- Ready-to-use environment configurations for RL and imitation learning

---

## Key Changes from Original Robocasa
- Added **G1 URDF** and mesh assets
- Updated robot model loader to support G1 joint naming & limits
- Tuned tabletop task scene layouts to match G1’s manipulation range

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/Robocasa-g1.git
   cd Robocasa-g1

