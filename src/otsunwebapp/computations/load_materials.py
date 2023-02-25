import io
import logging
import sys
import os
sys.path.append("/usr/lib/freecad")
sys.path.append("/usr/lib/freecad/lib")
import FreeCAD
import otsun
import numpy as np
import time

logger=logging.getLogger(__name__)

def get_material_and_movement(label):
    start = label.find("(")
    end = label.find(")")
    if (start == -1) or (end == -1):
        return None
    # print(label,start,end)
    material_and_movement = label[start+1:end]
    comma_pos = material_and_movement.find(',')
    if comma_pos > 0:
        has_movement = True
        name = material_and_movement[:comma_pos]
    else:
        has_movement = False
        name = material_and_movement
    return name, has_movement



def computation(data, root_folder):
    files_folder = os.path.join(root_folder, 'files')
    freecad_file = os.path.join(files_folder, data['freecad_file'])
    FreeCAD.openDocument(freecad_file)
    doc = FreeCAD.ActiveDocument
    objects = doc.Objects

    solid_material_labels = []
    faces_material_labels = []
    has_movement = False
    for obj in objects:
        # noinspection PyNoneFunctionAssignment
        label = obj.Label
        mat_mov = get_material_and_movement(label)
        if mat_mov is None:
            continue
        name, moves = mat_mov
        has_movement |= moves
        solids = obj.Shape.Solids
        faces = obj.Shape.Faces
        if solids:  # Object is a solid
            solid_material_labels.append(name)
        else:  # Object is made of faces
            faces_material_labels.append(name)
    data['solid_material_labels'] = list(set(solid_material_labels))
    data['faces_material_labels'] = list(set(faces_material_labels))
    data['scene_has_movement'] = has_movement
    logger.info("Found solids %s and faces %s", data['solid_material_labels'], data['faces_material_labels'])
    logger.info("Scene has movement: %s", data['scene_has_movement'])
    FreeCAD.closeDocument(doc.Name)

    return data

