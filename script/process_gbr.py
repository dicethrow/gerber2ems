""" Module containing functions for importing gerbers """
import subprocess
import os
import logging
from typing import List
import sys
import re

import cv2
import numpy as np
from nanomesh import Image
from nanomesh import Mesher2D

from constants import GEOMETRY_DIR, UNIT, PIXEL_SIZE

logger = logging.getLogger(__name__)


def process():
    """Processes all gerber files"""
    logger.info("Processing gerber files")

    files = os.listdir(os.getcwd())

    edge = next(filter(lambda name: "Edge_Cuts.gbr" in name, files), None)
    if edge is None:
        logger.error("No edge_cuts gerber found")
        sys.exit(1)

    layers = list(filter(lambda name: "_Cu.gbr" in name, files))
    if len(layers) == 0:
        logger.warning("No copper gerbers found")

    for name in layers:
        output = name.split("-")[-1].split(".")[0] + ".png"
        gbr_to_png(name, edge, os.path.join(os.getcwd(), GEOMETRY_DIR, output))


def gbr_to_png(gerber: str, edge: str, output: str) -> None:
    """Generate PNG from gerber file"""
    logger.debug("Generating PNG for %s", gerber)
    not_cropped_name = os.path.join(os.getcwd(), GEOMETRY_DIR, "not_cropped.png")

    dpi = 1 / (PIXEL_SIZE * UNIT / 0.0254)
    if not dpi.is_integer():
        logger.warning("DPI is not an integer number: %f", dpi)

    subprocess.call(
        f"gerbv {gerber} {edge} --background=#ffffff --foreground=#000000ff --foreground=#ff00000f -o {not_cropped_name} --dpi={dpi} --export=png -a",
        shell=True,
    )
    subprocess.call(f"convert {not_cropped_name} -trim {output}", shell=True)
    os.remove(not_cropped_name)


def get_triangles(input_name: str) -> np.ndarray:
    """Finds outlines in the image"""

    path = os.path.join(GEOMETRY_DIR, input_name)
    image = cv2.imread(path)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 230, 255, cv2.THRESH_BINARY_INV)

    plane = Image(thresh)

    mesher = Mesher2D(plane)
    mesher.generate_contour(max_edge_dist=1000)
    mesher.plot_contour()
    mesh = mesher.triangulate(opts="a100000")

    points = mesh.get("triangle").points
    cells = mesh.get("triangle").cells
    kinds = mesh.get("triangle").cell_data["physical"]

    triangles: np.ndarray = np.empty((len(cells), 3, 2))
    for i, cell in enumerate(cells):
        triangles[i] = [points[cell[0]], points[cell[1]], points[cell[2]]]

    mask = kinds == 2.0

    return triangles[mask]


def get_vias() -> List[List[float]]:
    """Get via information from excellon file"""
    files = os.listdir(os.getcwd())
    drill_filename = next(filter(lambda name: "-PTH.drl" in name, files), None)
    if drill_filename is None:
        logger.error("Couldn't find drill file")
        sys.exit(1)

    drills = {0: 0.0}  # Drills are numbered from 1. 0 is added as a "no drill" option
    current_drill = 0
    vias: List[List[float]] = []
    with open(drill_filename, "r", encoding="utf-8") as drill_file:
        for line in drill_file.readlines():
            match = re.fullmatch("T([0-9]+)C([0-9]+.[0-9]+)\\n", line)
            if match is not None:
                drills[int(match.group(1))] = float(match.group(2)) * 1000
            match = re.fullmatch("T([0-9]+)\\n", line)
            if match is not None:
                current_drill = int(match.group(1))
            match = re.fullmatch("X([0-9]+.[0-9]+)Y([0-9]+.[0-9]+)\\n", line)
            if match is not None:
                if current_drill in drills:
                    vias.append(
                        [
                            float(match.group(1)) * 1000,
                            float(match.group(2)) * 1000,
                            drills[current_drill],
                        ]
                    )
                else:
                    logger.warning(
                        "Drill file parsing failed. Drill with specifed number wasn't found"
                    )
    return vias
