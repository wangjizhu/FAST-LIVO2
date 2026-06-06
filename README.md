# FAST-LIVO2

> **`dashuai` 分支说明**：本分支由 **Claude Opus 4.8** 将原项目从 ROS1 (catkin) 转换为 **ROS2 (ament_cmake / rclcpp) 兼容**状态。
> The `dashuai` branch ports the original project from ROS1 (catkin) to **ROS2 (ament_cmake / rclcpp)** using **Claude Opus 4.8**.

## FAST-LIVO2: Fast, Direct LiDAR-Inertial-Visual Odometry

### 📢 News

- 🔓 **2025-01-23**: Code released!  
- 🎉 **2024-10-01**: Accepted by **T-RO '24**!  
- 🚀 **2024-07-02**: Conditionally accepted.

### 📬 Contact

For further inquiries or assistance, please contact [zhengcr@connect.hku.hk](mailto:zhengcr@connect.hku.hk).

## 1. Introduction

FAST-LIVO2 is an efficient and accurate LiDAR-inertial-visual fusion localization and mapping system, demonstrating significant potential for real-time 3D reconstruction and onboard robotic localization in severely degraded environments.

**Developer**: [Chunran Zheng 郑纯然](https://github.com/xuankuzcr)

<div align="center">
    <img src="pics/Framework.png" width = 100% >
</div>

### 1.1 Related video

Our accompanying video is now available on [**Bilibili**](https://www.bilibili.com/video/BV1Ezxge7EEi) and [**YouTube**](https://youtu.be/6dF2DzgbtlY).

### 1.2 Related paper

[FAST-LIVO2: Fast, Direct LiDAR-Inertial-Visual Odometry](https://arxiv.org/pdf/2408.14035)  

[FAST-LIVO2 on Resource-Constrained Platforms](https://arxiv.org/pdf/2501.13876)  

[FAST-LIVO: Fast and Tightly-coupled Sparse-Direct LiDAR-Inertial-Visual Odometry](https://arxiv.org/pdf/2203.00893)

[FAST-Calib: LiDAR-Camera Extrinsic Calibration in One Second](https://www.arxiv.org/pdf/2507.17210)

### 1.3 Our hard-synchronized equipment

We open-source our handheld device, including CAD files, synchronization scheme, STM32 source code, wiring instructions, and sensor ROS driver. Access these resources at this repository: [**LIV_handhold**](https://github.com/xuankuzcr/LIV_handhold).

### 1.4 Our associate dataset: FAST-LIVO2-Dataset
Our associate dataset [**FAST-LIVO2-Dataset**](https://connecthkuhk-my.sharepoint.com/:f:/g/personal/zhengcr_connect_hku_hk/ErdFNQtjMxZOorYKDTtK4ugBkogXfq1OfDm90GECouuIQA?e=KngY9Z) used for evaluation is also available online.

### 1.5 Our LiDAR-camera calibration method
The [**FAST-Calib**](https://github.com/hku-mars/FAST-Calib) toolkit is recommended. Its output extrinsic parameters can be directly filled into the YAML file. 

## 2. Prerequisited

### 2.1 Ubuntu and ROS2

Ubuntu 20.04 / 22.04 with **ROS2** (Foxy / Humble). [ROS2 Installation](https://docs.ros.org/en/humble/Installation.html).

> This `dashuai` branch targets **ROS2 (ament_cmake / rclcpp)**. For the original ROS1 (catkin) version, check out the `main` branch.

### 2.2 PCL && Eigen && OpenCV

PCL>=1.8, Follow [PCL Installation](https://pointclouds.org/). 

Eigen>=3.3.4, Follow [Eigen Installation](https://eigen.tuxfamily.org/index.php?title=Main_Page).

OpenCV>=4.2, Follow [Opencv Installation](http://opencv.org/).

### 2.3 Sophus

Sophus Installation for the non-templated/double-only version.

```bash
git clone https://github.com/strasdat/Sophus.git
cd Sophus
git checkout a621ff
mkdir build && cd build && cmake ..
make
sudo make install
```

### 2.4 Vikit

Vikit contains camera models, some math and interpolation functions that we need. This branch only uses **`vikit_common`** (the ROS-agnostic camera/math library) — the ROS1 `vikit_ros` camera-loader has been replaced by a self-contained, node-parameter-based camera loader inside this package. Build a ROS2 (ament) port of `vikit_common` in your ROS2 workspace `src` folder.

```bash
# Different from the one used in fast-livo1; build it for ROS2 (ament).
cd ~/ros2_ws/src
git clone https://github.com/xuankuzcr/rpg_vikit.git
```

> Note: `vikit_common`'s `PinholeCamera` / `EquidistantCamera` constructors are assumed to take `(width, height, scale, fx, fy, cx, cy, <distortion...>)`. If your `vikit_common` fork differs, adjust the camera construction block in `src/LIVMapper.cpp` (`initializeComponents`).

### 2.5 livox_ros_driver2

This branch depends on the ROS2 Livox driver [**livox_ros_driver2**](https://github.com/Livox-SDK/livox_ros_driver2) (provides `livox_ros_driver2/msg/CustomMsg`). Build and source it before building this package.

## 3. Build

Clone the repository and build with colcon:

```
cd ~/ros2_ws/src
git clone -b dashuai https://github.com/wangjizhu/FAST-LIVO2
cd ..
colcon build --symlink-install
source install/setup.bash
```

Make sure `vikit_common` and `livox_ros_driver2` are present in the same workspace (or already sourced) before building.

## 4. Run our examples

Download FAST-LIVO2-Dataset from [Global-LVBA](https://github.com/xuankuzcr/Global-LVBA) Section IV.

```
ros2 launch fast_livo mapping_avia.launch.py
ros2 bag play YOUR_DOWNLOADED_BAG
```

> ROS2 uses the `ros2 bag` format (sqlite3/mcap). To replay an original ROS1 `.bag`, convert it first (e.g. with [`rosbags-convert`](https://gitlab.com/ternaris/rosbags)) or play it through the `ros1_bridge`.


## 5. License

The source code of this package is released under the [**GPLv2**](http://www.gnu.org/licenses/) license. For commercial use, please contact me at <zhengcr@connect.hku.hk> and Prof. Fu Zhang at <fuzhang@hku.hk> to discuss an alternative license.
