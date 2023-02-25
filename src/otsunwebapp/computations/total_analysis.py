import logging
import sys
import os
sys.path.append("/usr/lib/freecad")
sys.path.append("/usr/lib/freecad/lib")
import FreeCAD
import otsun
import numpy as np
import time
from multiprocessing import Queue, Manager
from src.otsunwebapp.utils.my_multiprocessing import Process
from src.otsunwebapp.utils.statuslogger import StatusLogger
from collections import Counter

logger = logging.getLogger(__name__)
N_CPU = 20
MAX_RAYS_PER_COMPUTATION = 50000
GLOBAL_MAXIMUM_RAYS = 100000000

def data_consumer(common_data):
    data = []
    while True:
        m = common_data['data_consumer_queue'].get()
        if m == 'kill':
            logger.info("Finished getting results")
            break
        logger.debug(f"appending {m}")
        data.append(m)
    # data.sort()
    accumulated_energy_Th = Counter()
    accumulated_energy_PV = Counter()
    ph_dict = dict()
    th_dict = dict()
    aperture_dict = dict()
    identifiers = set()
    for (identifier, ph, th, captured_energy_Th, captured_energy_PV, aperture) in data:
        ph_dict[identifier] = ph
        th_dict[identifier] = th
        aperture_dict[identifier] = aperture
        accumulated_energy_Th[identifier] += captured_energy_Th
        accumulated_energy_PV[identifier] += captured_energy_PV
        identifiers.add(identifier)

    power_emitted_by_m2 = otsun.integral_from_data_file(common_data['data_file_spectrum'])

    efficiency_from_source_th_dict = dict()
    efficiency_from_source_pv_dict = dict()
    for identifier in sorted(identifiers):
        if common_data['aperture_collector_Th'] != 0.0:
            efficiency_from_source_th_dict[identifier] = \
                ((accumulated_energy_Th[identifier] / common_data['aperture_collector_Th']) /
                 (common_data['number_of_rays'] / aperture_dict[identifier]))
        else:
            efficiency_from_source_pv_dict[identifier] = 0.0
        if common_data['aperture_collector_PV'] != 0.0:
            efficiency_from_source_pv_dict[identifier] = \
                ((accumulated_energy_PV[identifier] / common_data['aperture_collector_PV']) /
                 (common_data['number_of_rays'] / aperture_dict[identifier]))
        else:
            efficiency_from_source_pv_dict[identifier] = 0.0

    logger.info("Writing files")
    with open(os.path.join(common_data['destfolder'],
                           'efficiency_results.txt'), 'w') as outfile_efficiency_results:
        outfile_efficiency_results.write(
            "%s %s" % (common_data['aperture_collector_Th'] * 0.001 * 0.001,
                       "# Collector Th aperture in m2") + '\n')
        outfile_efficiency_results.write(
            "%s %s" % (common_data['aperture_collector_PV'] * 0.001 * 0.001,
                       "# Collector PV aperture in m2") + '\n')
        outfile_efficiency_results.write("%s %s" % (power_emitted_by_m2,
                                                    "# Source power emitted by m2") + '\n')
        outfile_efficiency_results.write("%s %s" % (common_data['number_of_rays'],
                                                    "# Rays emitted")+ '\n')
        outfile_efficiency_results.write("%s %s" % (common_data['CSR'], "# CSR value") + '\n')
        outfile_efficiency_results.write("%s %s" % (common_data['freecad_file'],
                                                    "# FreeCAD file") + '\n')
        outfile_efficiency_results.write("%s %s" % (common_data['materials_file'],
                                                    "# Materials file") + '\n')
        outfile_efficiency_results.write("%s" % (
            "#phi theta efficiency_from_source_Th efficiency_from_source_PV") + '\n')
        for identifier in sorted(identifiers):
            ph = ph_dict[identifier]
            th = th_dict[identifier]
            eff_th = efficiency_from_source_th_dict[identifier]
            eff_pv = efficiency_from_source_pv_dict[identifier]

            outfile_efficiency_results.write("%.3f %.3f %.6f %.6f\n" % (ph, th, eff_th, eff_pv))


def compute(*args):
    identifier, current_rays, ph, th, common_data = args

    main_direction = otsun.polar_to_cartesian(ph, th) * -1.0  # Sun direction vector

    if common_data['move_elements']:
        tracking = otsun.MultiTracking(main_direction, common_data['current_scene'])
        tracking.make_movements()

    emitting_region = otsun.GeneralizedSunWindow(common_data['current_scene'], main_direction)
    l_s = otsun.LightSource(common_data['current_scene'], emitting_region, common_data['light_spectrum'], 1.0,
                            common_data['direction_distribution'],
                            common_data['polarization_vector'])

    exp = otsun.Experiment(common_data['current_scene'], l_s,
                           current_rays, common_data['show_in_doc'])
    logger.info("launching experiment %s", [os.getpid(), ph, th, main_direction])
    try:
        exp.run()
    except:
        logger.error("experiment ended with an error")
        raise Exception
    # if common_data['aperture_collector_Th'] != 0.0:
    #     efficiency_from_source_th = (exp.captured_energy_Th / common_data['aperture_collector_Th']) / (
    #             exp.number_of_rays / exp.light_source.emitting_region.aperture)
    # else:
    #     efficiency_from_source_th = 0.0
    # if common_data['aperture_collector_PV'] != 0.0:
    #     efficiency_from_source_pv = (exp.captured_energy_PV / common_data['aperture_collector_PV']) / (
    #             exp.number_of_rays / exp.light_source.emitting_region.aperture)
    # else:
    #     efficiency_from_source_pv = 0.0
    common_data['data_consumer_queue'].put((identifier, ph, th, exp.captured_energy_Th, exp.captured_energy_PV,
                                            l_s.emitting_region.aperture))

    if common_data['move_elements']:
        tracking.undo_movements()

    common_data['statuslogger'].increment()


def computation(data, root_folder):

    logger.info("experiment from total_analysis got called")

    #
    # Prepare common data
    #

    common_data = {}

    manager = Manager()
    common_data['statuslogger'] = StatusLogger(manager, 0, root_folder)

    common_data['data_consumer_queue'] = Queue()


    _ROOT = os.path.abspath(os.path.dirname(__file__))

    common_data['data_file_spectrum'] = os.path.join(_ROOT, 'data', 'ASTMG173-direct.txt')
    common_data['light_spectrum'] = otsun.cdf_from_pdf_file(common_data['data_file_spectrum'])

    common_data['destfolder'] = os.path.join(root_folder, 'output')
    try:
        os.makedirs(common_data['destfolder'])
    except:
        pass  # we suppose it already exists

    if data['CSR'] == "":
        common_data['direction_distribution'] = None # default option main_direction
        common_data['CSR'] = "None"
    else:
        CSR = float(data['CSR'])
        Buie_model = otsun.buie_distribution(CSR)
        common_data['direction_distribution'] = Buie_model
        common_data['CSR'] = CSR


    common_data['show_in_doc'] = None

    common_data['number_of_rays'] = int(data['numrays'])

    if data['aperture_pv'] == "":
        common_data['aperture_collector_PV'] = 0
    else:
        common_data['aperture_collector_PV'] = float(data['aperture_pv'])

    if data['aperture_th'] == "":
        common_data['aperture_collector_Th'] = 0
    else:
        common_data['aperture_collector_Th'] = float(data['aperture_th'])

    common_data['move_elements'] = data.get('move_scene', 'no') == 'yes'

    common_data['polarization_vector'] = None

    #
    # Load parameters from user input
    #

    phi_ini = float(data['phi_ini']) + 1.E-9
    phi_end = float(data['phi_end']) + 1.E-4
    if data['phi_step'] == "" or float(data['phi_step'])==0:
        phi_step = 1.0
    else:
        phi_step = float(data['phi_step'])

    theta_ini = float(data['theta_ini']) + 1.E-9
    theta_end = float(data['theta_end']) + 1.E-4
    if data['theta_step'] == "" or float(data['theta_step']==0):
        theta_step = 1.0
    else:
        theta_step = float(data['theta_step'])

    #
    # Load document and materials
    #

    files_folder = os.path.join(root_folder, 'files')
    freecad_file = os.path.join(files_folder, data['freecad_file'])
    materials_file = os.path.join(files_folder, data['materials_file'])

    common_data['freecad_file'] = os.path.basename(freecad_file)
    common_data['materials_file'] = os.path.basename(materials_file)

    otsun.Material.by_name = {}
    otsun.Material.load_from_json_zip(materials_file)

    doc = FreeCAD.openDocument(freecad_file)
    sel = doc.Objects

    common_data['current_scene'] = otsun.Scene(sel)

    #
    # Prepare computations
    #

    list_pars = []
    identifier = 0
    total_rays = common_data['number_of_rays']

    num_phi = (phi_end - phi_ini)/phi_step + 1
    num_theta = (theta_end - theta_ini)/theta_step + 1
    global_number_rays = total_rays * num_phi * num_theta
    if global_number_rays > GLOBAL_MAXIMUM_RAYS:
        total_rays = int(GLOBAL_MAXIMUM_RAYS / (num_theta*num_phi))
        warn_user(common_data,
                  "Warning.txt",
                  f"Adjusting the number of rays to {total_rays} (maximum exceeded)\n")
        logger.warning(f"Adjusting the number of rays to {total_rays} (maximum exceeded)")
    for ph in np.arange(phi_ini, phi_end, phi_step):
        for th in np.arange(theta_ini, theta_end, theta_step):
            pending_rays = total_rays
            while pending_rays > 0:
                current_rays = min(MAX_RAYS_PER_COMPUTATION, pending_rays)
                pending_rays -= current_rays
                list_pars.append((identifier, current_rays, ph, th, common_data))
            identifier += 1

    common_data['statuslogger'].total = len(list_pars)

    #
    # Prepare consumer
    #

    data_consumer_process = Process(target=data_consumer, args=(common_data,))
    data_consumer_process.start()

    #
    # Launch computations
    #
    remaining = list_pars[:]
    active_processes = []
    while remaining:
        for p in active_processes:
            if not p.is_alive():
                active_processes.remove(p)
                if p.exception:
                    logger.error("Catched child error phase 1")
                    error, traceback = p.exception
                    # print(traceback)
                    common_data['statuslogger'].data = {'status': 'error', 'percentage': 'N/A'}
                    common_data['statuslogger'].save()
                    raise error
        free_slots = N_CPU - len(active_processes)
        # print(f"{free_slots} free slots")
        process_now = remaining[:free_slots]
        remaining = remaining[free_slots:]
        for args in process_now:
            p = Process(target=compute, args=args)
            p.start()
            active_processes.append(p)
        time.sleep(0.1)
    logger.info("All tasks queued")

    #
    # Finish computations and consumer
    #

    for p in active_processes:
        p.join()
        if p.exception:
            logger.error("Catched child error phase 2")
            error, traceback = p.exception
            common_data['statuslogger'].data = {'status': 'error', 'percentage': 'N/A'}
            common_data['statuslogger'].save()
            # print(traceback)
            raise error
    logger.info("Putting poison")
    common_data['data_consumer_queue'].put('kill')
    data_consumer_process.join()
    FreeCAD.closeDocument(doc.Name)

def warn_user(common_data, filename, message):
    with open(os.path.join(common_data['destfolder'], filename), 'w') as f:
        f.write(message)