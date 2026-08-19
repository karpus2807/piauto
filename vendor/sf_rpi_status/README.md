# SF RPi Status

SunFounder Raspberry Pi Status is a tool to get the status of your Raspberry Pi. It has cli commands functions

- [SF RPi Status](#sf-rpi-status)
  - [Installation](#installation)
  - [Usage](#usage)
  - [About SunFounder](#about-sunfounder)
  - [Contact us](#contact-us)


## Installation

```bash
# Install development dependencies
apt-get -y install python3 python3-pip python3-venv git
# Create a virtual environment
python3 -m venv venv
# Install build
pip3 install build

# Clone the repository
git clone https://github.com/sunfounder/sf_rpi_status.git
# Activate the virtual environment
source venv/bin/activate
# build the package
python3 -m build
# Install the package
pip3 install dist/*.whl
```

## Usage

```bash
# Activate the virtual environment
source venv/bin/activate
# Check the status CPU
sf_rpi_status --cpu
# Check all
sf_rpi_status --all
# See more options
sf_rpi_status --help
```

## About SunFounder
SunFounder is a company focused on STEAM education with products like open source robots, development boards, STEAM kit, modules, tools and other smart devices distributed globally. In SunFounder, we strive to help elementary and middle school students as well as hobbyists, through STEAM education, strengthen their hands-on practices and problem-solving abilities. In this way, we hope to disseminate knowledge and provide skill training in a full-of-joy way, thus fostering your interest in programming and making, and exposing you to a fascinating world of science and engineering. To embrace the future of artificial intelligence, it is urgent and meaningful to learn abundant STEAM knowledge.

## Contact us
website:
    www.sunfounder.com

E-mail:
    service@sunfounder.com
