import sys
import otsun
import logging
import os
sys.path.append("/usr/lib/freecad")
sys.path.append("/usr/lib/freecad/lib")
import FreeCAD
import numpy as np
import multiprocessing
from multiprocessing import Process
from otsunwebapp.utils.statuslogger import StatusLogger

logger = logging.getLogger(__name__)


def compute(*args):
    data, root_folder = args
    global doc
    global current_scene

    manager = multiprocessing.Manager()
    statuslogger = StatusLogger(manager, 0, root_folder)

    logger.info("experiment from drawing_experiment got called")
    _ROOT = os.path.abspath(os.path.dirname(__file__))
#    data_file_spectrum = os.path.join(_ROOT, 'data', 'ASTMG173-direct.txt')
    destfolder = os.path.join(root_folder, 'output')
    try:
        os.makedirs(destfolder)
    except:
        pass  # we suppose it already exists

    polarization_vector = None
    phi = float(data['phi'])
    theta = float(data['theta'])
    wavelength = float(data['wavelength'])
    number_of_rays = int(data['numrays'])

    if data['aperture_pv'] == "":
        aperture_collector_PV = 0
    else:
        aperture_collector_PV = float(data['aperture_pv'])

    if data['aperture_th'] == "":
        aperture_collector_Th = 0
    else:
        aperture_collector_Th = float(data['aperture_th'])

    # ---
    # Inputs for Drawing Experiment
    # ---
    # for direction of the source two options: Buie model or main_direction
    if data['CSR'] == "":
        direction_distribution = None # default option main_direction
    else:
        CSR = float(data['CSR'])
        Buie_model = otsun.buie_distribution(CSR)
        direction_distribution = Buie_model
    # --------- end

    files_folder = os.path.join(root_folder, 'files')
    freecad_file = os.path.join(files_folder, data['freecad_file'])
    materials_file = os.path.join(files_folder, data['materials_file'])

    otsun.Material.by_name = {}
    otsun.Material.load_from_json_zip(materials_file)
    doc = FreeCAD.openDocument(freecad_file)
    show_in_doc = doc
    sel = doc.Objects
    current_scene = otsun.Scene(sel)

    # ---
    # Magnitudes used for outputs in Spectral Analysis
    # ---
    captured_energy_PV = 0.0
    captured_energy_Th = 0.0
    source_wavelength = []
    Th_energy = []
    Th_wavelength = []
    PV_energy = []
    PV_wavelength = []
    PV_values = []
    # --------- end

    number_of_runs = 1

    statuslogger.total = number_of_runs
    w = wavelength
    light_spectrum = w
    main_direction = otsun.polar_to_cartesian(phi, theta) * -1.0  # Sun direction vector

    move_elements = data.get('move_scene','no') == 'yes'

    if move_elements:
        tracking = otsun.MultiTracking(main_direction, current_scene)
        tracking.make_movements()
    emitting_region = otsun.GeneralizedSunWindow(current_scene, main_direction)
    l_s = otsun.LightSource(current_scene, emitting_region, light_spectrum, 1.0, direction_distribution,
                               polarization_vector)
    exp = otsun.Experiment(current_scene, l_s, number_of_rays, show_in_doc)
    logger.info("launching experiment %s", [w, main_direction])
    try:
        exp.run(show_in_doc)
    except:
        logger.error("computation ended with an error")

    Th_energy.append(exp.Th_energy)
    Th_wavelength.append(exp.Th_wavelength)
    PV_energy.append(exp.PV_energy)
    PV_wavelength.append(exp.PV_wavelength)
    source_wavelength.append(w)
    if exp.PV_values:
        PV_values.append(exp.PV_values)
    captured_energy_PV += exp.captured_energy_PV
    captured_energy_Th += exp.captured_energy_Th

    statuslogger.increment()

    all_obj = doc.Objects
    for obj in all_obj:
        logger.debug('Object %s', obj.Name)

    doc.recompute()
    doc.saveAs(os.path.join(destfolder,'drawing.FCStd'))

    # Close document
    FreeCAD.closeDocument(doc.Name)
    # ---
    # Output file for wavelengths emitted by the source
    # ---
    data_source_wavelength = np.array(source_wavelength)
    data_source_wavelength = data_source_wavelength.T
    source_wavelengths_file = os.path.join(destfolder, 'source_wavelengths.txt')
    with open(source_wavelengths_file, 'w') as outfile_source_wavelengths:
        outfile_source_wavelengths.write(
            "%s %s\n" % (aperture_collector_Th * 0.001 * 0.001, "# Collector Th aperture in m2"))
        outfile_source_wavelengths.write(
            "%s %s\n" % (aperture_collector_PV * 0.001 * 0.001, "# Collector PV aperture in m2"))
        outfile_source_wavelengths.write("%s %s\n" % (wavelength, "# Wavelength in nm"))
        outfile_source_wavelengths.write("%s %s\n" % (number_of_rays, "# Rays to plot"))
        outfile_source_wavelengths.write("%s %s\n" % (data['phi'], "# Phi (solar azimuth angle)"))
        outfile_source_wavelengths.write("%s %s\n" % (data['theta'], "# Theta (solar zenith angle)"))
        outfile_source_wavelengths.write("%s %s\n" % (data['CSR'], "# CSR value"))
        outfile_source_wavelengths.write("%s %s\n" % (data['freecad_file'], "# FreeCAD file"))
        outfile_source_wavelengths.write("%s %s\n" % (data['materials_file'], "# Materials file"))
    # --------- end
    # ---


def computation(data, root_folder):
    p = Process(target=compute, args=(data, root_folder))
    p.start()
    p.join()