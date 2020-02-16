# MIT License
#
# Copyright (c) 2019 Robert Gützkow
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import colors
import file_io
import mapping
import argparse
import os
import bisect
from typing import List
from abc import ABC, abstractmethod


class LutGeneratorBase(ABC):
    """
    Abstract base class for all lookup table generators
    """
    def __init__(self, output, test):
        self.output = output
        self.test = test

    @abstractmethod
    def save_spi3d(self):
        pass

    @staticmethod
    def generate_spi3d_from_colormap(colormap,
                                     cube_size=65,
                                     input_exp_range=(-12.473931189, 4.026068812),
                                     unclipped_exp_range=(-12.473931189, 4.026068812),
                                     centered=False):
        """
        Generates the false color 3D LUT for Blender based on the given colormap.
        :param colormap: Colormap to use for the LUT
        :param cube_size: [0, cube_size-1] is the range of input samples per channel in the generated LUT
        :param input_exp_range: Ordered tuple of the two exponents defining the input value range
        :param unclipped_exp_range: Ordered tuple of exponents defining the input value range that won't be
            clipped
        :param centered: The input value for middle grey is mapped to the center of the colormap, if set to True
        :return: Generated LUT as list of strings
        """
        lut = ["SPILUT 1.0\n", "3 3\n", f"{cube_size} {cube_size} {cube_size}\n"]
        for in_red in range(0, cube_size):
            for in_green in range(0, cube_size):
                for in_blue in range(0, cube_size):
                    red = in_red / (cube_size - 1)
                    green = in_green / (cube_size - 1)
                    blue = in_blue / (cube_size - 1)
                    y = colors.relative_luminance(red, green, blue)

                    low_clip = colors.normalize_value(2 ** unclipped_exp_range[0],
                                                      input_exp_range[0],
                                                      input_exp_range[1])
                    high_clip = colors.normalize_value(2 ** unclipped_exp_range[1],
                                                       input_exp_range[0],
                                                       input_exp_range[1])
                    if y < low_clip:
                        color = colors.get_color(colormap, 0.0)
                    elif y > high_clip:
                        color = colors.get_color(colormap, 1.0)
                    else:
                        if centered:
                            mapped = mapping.map_to_colormap_range(y,
                                                                   input_exp_range[0],
                                                                   input_exp_range[1])
                        else:
                            mapped = y
                        color = colors.get_color(colormap, mapped)

                    lut.append(f"{in_red} {in_blue} {in_green} {color[0]:.8f} {color[1]:.8f} {color[2]:.8f}\n")
        return lut

    @staticmethod
    def generate_spi3d_from_evs(ev_colormap: List[colors.ColorPoint],
                                cube_size=65,
                                input_exp_range=(-12.473931189, 4.026068812)):
        """
        Generates the false color 3D LUT for Blender based on the given exposure values and associated colors.
        :param ev_colormap: Colormap consisting of exposure values and associated color
        :param cube_size: [0, cube_size-1] is the range of input samples per channel in the generated LUT
        :param input_exp_range: Ordered tuple of the two exponents defining the input value range
        :return: Generated LUT as list of strings
        """
        ev_colormap = sorted(ev_colormap, key=lambda x: x.coordinate)
        coordinates = []
        for ev_to_color in ev_colormap:
            ev_to_color.coordinate = colors.normalize_value(2 ** ev_to_color.coordinate * 0.18,
                                                            input_exp_range[0],
                                                            input_exp_range[1])
            coordinates.append(ev_to_color.coordinate)  # Required for bisect

        lut = ["SPILUT 1.0\n", "3 3\n", f"{cube_size} {cube_size} {cube_size}\n"]
        for in_red in range(0, cube_size):
            for in_green in range(0, cube_size):
                for in_blue in range(0, cube_size):
                    red = in_red / (cube_size - 1)
                    green = in_green / (cube_size - 1)
                    blue = in_blue / (cube_size - 1)
                    y = colors.relative_luminance(red, green, blue)

                    idx_right_neighbor = bisect.bisect(coordinates, y)

                    if idx_right_neighbor == 0:
                        color = ev_colormap[idx_right_neighbor].get_color(y)
                    elif idx_right_neighbor == len(coordinates):
                        color = ev_colormap[idx_right_neighbor - 1].get_color(y)
                    else:
                        idx_left_neighbor = idx_right_neighbor - 1
                        factor = ((y - coordinates[idx_left_neighbor]) /
                                  (coordinates[idx_right_neighbor] - coordinates[idx_left_neighbor]))

                        color = colors.interpolate(ev_colormap[idx_left_neighbor].get_color(y),
                                                   ev_colormap[idx_right_neighbor].get_color(y),
                                                   factor)

                    lut.append(f"{in_red} {in_blue} {in_green} {color[0]:.8f} {color[1]:.8f} {color[2]:.8f}\n")
        return lut

    @staticmethod
    def print_colormap(name, colormap):
        for idx, element in enumerate(colormap):
            if idx == 0:
                print(f"{name} = [{element},")
            elif idx < len(colormap) - 1:
                print(f"{element},")
            else:
                print(f"{element}]")


class LutGeneratorSingleLutBase(LutGeneratorBase):
    """
    Abstract class for all lookup table generators that produce a single lookup table
    """
    def __init__(self, output, test, name):
        self.name = name
        super().__init__(output, test)

    @abstractmethod
    def get_colormap(self):
        pass

    @abstractmethod
    def generate_lut(self):
        pass

    def save_spi3d(self):
        """
        Generate and save the lookup table in the spi3d format.
        :return:
        """
        lut = self.generate_lut()
        file_path = os.path.join(self.output, self.name)
        file_io.save_file(lut, file_path)


class LutGeneratorColormapBase(LutGeneratorSingleLutBase):
    """
    Abstract class for lookup table generators that use colormaps
    """
    def __init__(self, output, test, name, centered):
        self.centered = centered
        super().__init__(output, test, name)

    @abstractmethod
    def get_colormap(self):
        pass

    def generate_lut(self):
        """
        Generates the lookup table for the given colormap.
        :return: Lookup table in the spi3d format
        """
        colormap = self.get_colormap()

        if self.test:
            self.print_colormap(self.name, colormap)

        if self.centered:
            return self.generate_spi3d_from_colormap(colormap, centered=True)
        else:
            return self.generate_spi3d_from_colormap(colormap, centered=False)


class LutGeneratorColormapBlocksBase(LutGeneratorSingleLutBase):
    """
    Abstract class for lookup table generators that use exposure value based colormaps for constant color blocks
    between exposure values.
    """
    def __init__(self, output, test, name, block_type, exposure_values):
        self.block_type = block_type
        self.exposure_values = exposure_values
        super().__init__(output, test, name)

    @abstractmethod
    def get_colormap(self):
        pass

    def generate_lut(self):
        """
        Generates the lookup table for the given colormap by converting it into an exposure value based colormap with
        segments of constant color between the exposure values.
        :return: Lookup table in the spi3d format
        """
        colormap = self.get_colormap()

        if self.block_type == "equidistant":
            ev_colormap = colors.colormap_to_ev_blocks_equidistant(colormap, self.exposure_values)
            if self.test:
                self.print_colormap(self.name, ev_colormap)
            return self.generate_spi3d_from_evs(ev_colormap)
        elif self.block_type == "centered":
            ev_colormap = colors.colormap_to_ev_blocks_centered(colormap, self.exposure_values)
            if self.test:
                self.print_colormap(self.name, ev_colormap)
            return self.generate_spi3d_from_evs(ev_colormap)
        elif self.block_type == "stretched":
            ev_colormap = colors.colormap_to_ev_blocks_stretched(colormap, self.exposure_values)
            if self.test:
                self.print_colormap(self.name, ev_colormap)
            return self.generate_spi3d_from_evs(ev_colormap)


class LutGeneratorDefault(LutGeneratorBase):
    """
    Default lookup table generator that creates a spi3d file for every pre-defined colormap.
    """
    def __init__(self, output, test):
        super().__init__(output, test)

    def save_spi3d(self):
        """
        Generate and save a lookup table in the spi3d format for every pre-defined colormap.
        :return:
        """
        for filename, colormap in colors.colormaps.items():
            if self.test:
                self.print_colormap(filename, colormap)
            lut = self.generate_spi3d_from_colormap(colormap)
            file_path = os.path.join(self.output, filename)
            file_io.save_file(lut, file_path)

        for filename, ev_colormap in colors.ev_colormaps.items():
            if self.test:
                self.print_colormap(filename, ev_colormap)
            lut = self.generate_spi3d_from_evs(ev_colormap)
            file_path = os.path.join(self.output, filename)
            file_io.save_file(lut, file_path)


class LutGeneratorViscm(LutGeneratorColormapBase):
    """
    Lookup table generator based on a viscm colormap
    """
    def __init__(self, output, test, path, name, centered):
        self.path = path
        super().__init__(output, test, name, centered)

    def get_colormap(self):
        """
        Load the viscm colormap from the python script.
        :return: Colormap
        """
        return file_io.load_viscm_colormap(self.path)


class LutGeneratorViscmBlocks(LutGeneratorColormapBlocksBase):
    """
    Lookup table generator based on a viscm colormap for a LUT with segments of constant color between the
    given exposure values.
    """
    def __init__(self, output, test, path, name, block_type, exposure_values):
        self.path = path
        super().__init__(output, test, name, block_type, exposure_values)

    def get_colormap(self):
        """
        Load the viscm colormap from the python script.
        :return Colormap
        """
        return file_io.load_viscm_colormap(self.path)


class LutGeneratorColormap(LutGeneratorColormapBase):
    """
    Lookup table generator based on a colormap
    """
    def get_colormap(self):
        """
        Retrieve the pre-defined colormap by name.
        :return: Colormap
        """
        return colors.colormaps[self.name]


class LutGeneratorColormapBlocks(LutGeneratorColormapBlocksBase):
    """
    Lookup table generator based on a colormap for a LUT with segments of constant color between the given exposure
    values.
    """
    def get_colormap(self):
        """
        Retrieve the pre-defined colormap by name.
        :return: Colormap
        """
        return colors.colormaps[self.name]


class LutGeneratorEvColormap(LutGeneratorSingleLutBase):
    """
    Lookup table generater based on a colormap for specific exposure values
    """
    def get_colormap(self):
        """
        Retrieve the pre-defined colormap by name.
        :return: Colormap
        """
        return colors.ev_colormaps[self.name]

    def generate_lut(self):
        """
        Generates the lookup table for the given colormap.
        """
        colormap = self.get_colormap()

        if self.test:
            self.print_colormap(self.name, colormap)

        return self.generate_spi3d_from_evs(colormap)


class LutGeneratorFactory:
    """
    Factory for creating lookup table generators.
    """
    @staticmethod
    def make_lut_generator(args):
        """
        Makes a lookup table generator based on the supplied arguments
        :param args: Arguments
        :return: Lookup table generator
        """
        if args.sub is None:
            return LutGeneratorDefault(args.output, args.test)
        else:
            if args.sub == "ev-colormap":
                return LutGeneratorEvColormap(args.output, args.test, args.name)
            else:
                block_type = None
                exposure_values = []

                if args.blocks_centered is not None:
                    block_type = "centered"
                    exposure_values = args.blocks_centered
                elif args.blocks_equidistant is not None:
                    block_type = "equidistant"
                    exposure_values = args.blocks_equidistant
                elif args.blocks_stretched is not None:
                    block_type = "stretched"
                    exposure_values = args.blocks_stretched

                if block_type is not None:
                    if args.sub == "viscm":
                        return LutGeneratorViscmBlocks(args.output,
                                                       args.test,
                                                       args.path,
                                                       args.name,
                                                       block_type,
                                                       exposure_values)
                    elif args.sub == "colormap":
                        return LutGeneratorColormapBlocks(args.output,
                                                          args.test,
                                                          args.name,
                                                          block_type,
                                                          exposure_values)
                else:
                    if args.sub == "viscm":
                        return LutGeneratorViscm(args.output,
                                                 args.test,
                                                 args.path,
                                                 args.name,
                                                 args.centered)
                    elif args.sub == "colormap":
                        return LutGeneratorColormap(args.output,
                                                    args.test,
                                                    args.name,
                                                    args.centered)


def main(args):
    lut_generator = LutGeneratorFactory.make_lut_generator(args)
    lut_generator.save_spi3d()


def parse_args():
    parser = argparse.ArgumentParser(prog="False Color LUT Generator",
                                     description="Generates spi3d lookup tables for Blender's color management")

    parser.add_argument("-o",
                        "--output",
                        type=str,
                        help="Output directory for the generated LUTs",
                        required=True)
    parser.add_argument("-t",
                        "--test",
                        help="Print used colormap(s) to the console",
                        dest="test",
                        action="store_true",
                        required=False)

    parent_parser = argparse.ArgumentParser(add_help=False)
    group = parent_parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--centered",
                       help="Use the given colormap for a smooth gradient of colors. This options shifts the input "
                            "values, in order to map middle grey to the center of the colormap. The input also "
                            "has to be scaled after the shift to still fit within the [0.0, 1.0] range. This results "
                            "in parts of the colormap being unused, since the range from the minimum to EV 0 is larger "
                            "than the EV 0 to the maximum.",
                       dest="centered",
                       action="store_true")
    group.add_argument("--not-centered",
                       help="Use the given colormap for a smooth gradient of colors. The input range is mapped to the "
                            "color range without any shifts, using the full range of colors. Middle grey is therefore "
                            "not mapped to the center of the colormap.",
                       dest="centered",
                       action="store_false")
    group.add_argument("--blocks-equidistant",
                       type=lambda s: [float(x) for x in s.split(',')],
                       help="Create a constant color 'block' between each neighboring exposure values. "
                            "This option samples the colors for the exposure values from equidistant points on the "
                            "colormap. The argument for this flag should be a quoted and comma separated list of "
                            "exposure values, used for the sampling from the colormap, e.g. "
                            "'-10.0, -9.99, -7.5, -5.0, -2.5, -1.0, -0.1, 0.1, 1.0, 2.5, 5.0, 6.49, 6.50'")
    group.add_argument("--blocks-centered",
                       type=lambda s: [float(x) for x in s.split(',')],
                       help="Create a constant color 'block' between each neighboring exposure values. "
                            "This options shifts the input values, in order to map exposure value 0 (EV 0) to "
                            "the center of the colormap. The input also has to be scaled, after the shift, to still "
                            "fit within the [0.0, 1.0] range. This results in parts of the colormap being unused, "
                            "since the range from the minimum to EV 0 is larger than the EV 0 to the maximum. The "
                            "argument for this flag should be a quoted and comma separated list of exposure values, "
                            "used for the sampling from the colormap, e.g. "
                            "'-10.0, -9.99, -7.5, -5.0, -2.5, -1.0, -0.1, 0.1, 1.0, 2.5, 5.0, 6.49, 6.50'")
    group.add_argument("--blocks-stretched",
                       type=lambda s: [float(x) for x in s.split(',')],
                       help="Create a constant color 'block' between each neighboring exposure values. "
                            "This options shifts the input values, in order to map exposure value 0 (EV 0) to the "
                            "center of the colormap. The input also has to be scaled, after the shift, to still fit "
                            "within the [0.0, 1.0] range. The two halves, from the minimum to EV 0 and EV 0 to "
                            "the maximum, are scaled independently, in order to map the minimum to 0.0 and the maximum "
                            "to 1.0. This scaling is non-uniform / stretched. The argument for this flag should be a "
                            "quoted and comma separated list of exposure values, used for the sampling from the "
                            "colormap, e.g. "
                            "'-10.0, -9.99, -7.5, -5.0, -2.5, -1.0, -0.1, 0.1, 1.0, 2.5, 5.0, 6.49, 6.50'")

    subparser = parser.add_subparsers(help="Select a specific colormap for the LUT creation.", dest="sub")
    parser_viscm = subparser.add_parser("viscm",
                                        parents=[parent_parser],
                                        help="Load a colormap generated by viscm, which is stored as python script by "
                                             "the application")
    parser_viscm.add_argument("-p",
                              "--path",
                              type=str,
                              help="Path to the viscm generated colormap stored as python script",
                              required=True)

    parser_viscm.add_argument("-n",
                              "--name",
                              type=str,
                              help="Name of the viscm colormap. Will be used as output filename.",
                              required=True)

    parser_colormap = subparser.add_parser("colormap",
                                           parents=[parent_parser],
                                           help="Use one of the pre-defined colormaps.")
    parser_colormap.add_argument("-n",
                                 "--name",
                                 choices=colors.colormaps.keys(),
                                 help="Name of the pre-defined colormap.",
                                 required=True)

    parser_ev_colormap = subparser.add_parser("ev-colormap",
                                              help="Use one of the pre-defined exposure value colormaps.")
    parser_ev_colormap.add_argument("-n",
                                    "--name",
                                    choices=colors.ev_colormaps.keys(),
                                    help="Name of the pre-defined exposure value colormap",
                                    required=True)

    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    main(arguments)
