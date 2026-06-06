#!/usr/bin/env python3
# Launch file for the MARS-LVIG dataset (ROS2 port).
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('fast_livo')
    config = os.path.join(pkg_share, 'config', 'MARS_LVIG.yaml')
    camera_config = os.path.join(pkg_share, 'config', 'camera_MARS_LVIG.yaml')
    rviz_config = os.path.join(pkg_share, 'rviz_cfg', 'M300.rviz')

    rviz_arg = DeclareLaunchArgument('rviz', default_value='true')

    mapping_node = Node(
        package='fast_livo',
        executable='fastlivo_mapping',
        name='laserMapping',
        output='screen',
        parameters=[config, camera_config],
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz',
        arguments=['-d', rviz_config],
        condition=IfCondition(LaunchConfiguration('rviz')),
    )

    republish_node = Node(
        package='image_transport',
        executable='republish',
        name='republish',
        arguments=['compressed', 'raw'],
        remappings=[
            ('in/compressed', '/left_camera/image/compressed'),
            ('out', '/left_camera/image'),
        ],
        respawn=True,
    )

    return LaunchDescription([
        rviz_arg,
        mapping_node,
        rviz_node,
        republish_node,
    ])
