import logging
import sys
import os
sys.path.append("/usr/lib/freecad")
sys.path.append("/usr/lib/freecad/lib")
import FreeCAD
import otsun
import numpy as np
import time
from multiprocessing import Queue, Process, Manager
from src.otsunwebapp.utils.statuslogger import StatusLogger

logger = logging.getLogger(__name__)
N_CPU = 20
MAX_RAYS_PER_COMPUTATION = 50000


def data_consumer(common_data):
    data = []
    while True:
        m = common_data['data_consumer_queue'].get()
        if m == 'kill':
            logger.info("Finished getting results")
            break
        logger.debug(f"appending {m}")
        data.append(m)
    data.sort()

    captured_energy_PV = 0.0
    captured_energy_Th = 0.0
    source_wavelength = []
    Th_energy = []
    Th_wavelength = []
    Th_points_absorber = []
    PV_energy = []
    PV_wavelength = []
    PV_values = []

    for data_line in data:
        (w, exp_Th_energy, exp_Th_wavelength, exp_PV_energy, exp_PV_wavelength,
        exp_PV_values, exp_points_absorber_Th, exp_captured_energy_Th, exp_captured_energy_PV,
        aperture_source) = data_line
        Th_energy.append(exp_Th_energy)
        Th_wavelength.append(exp_Th_wavelength)
        PV_energy.append(exp_PV_energy)
        PV_wavelength.append(exp_PV_wavelength)
        source_wavelength.append(w)
        if exp_PV_values:
            PV_values.append(exp_PV_values)
        if exp_points_absorber_Th:
            Th_points_absorber.append(exp_points_absorber_Th)
        captured_energy_PV += exp_captured_energy_PV
        captured_energy_Th += exp_captured_energy_Th



    source_wavelengths_file = os.path.join(common_data['destfolder'], 'source_wavelengths.txt')
    with open(source_wavelengths_file, 'w') as outfile_source_wavelengths:
        outfile_source_wavelengths.write(
            f"{aperture_source} # Source wavelength aperture in m2\n"
        )
        outfile_source_wavelengths.write(
            "%s %s\n" % (common_data['aperture_collector_Th'] * 0.001 * 0.001, "# Collector Th aperture in m2"))
        outfile_source_wavelengths.write(
            "%s %s\n" % (common_data['aperture_collector_PV'] * 0.001 * 0.001, "# Collector PV aperture in m2"))
        outfile_source_wavelengths.write("%s %s\n" % (common_data['wavelength_ini'], "# Wavelength initial in nm"))
        outfile_source_wavelengths.write("%s %s\n" % (common_data['wavelength_end'], "# Wavelength final in nm"))
        outfile_source_wavelengths.write("%s %s\n" % (common_data['wavelength_step'], "# Step of wavelength in nm"))
        outfile_source_wavelengths.write("%s %s\n" % (common_data['number_of_rays'], "# Rays per wavelength"))
        outfile_source_wavelengths.write("%s %s\n" % (common_data['phi'], "# Phi (solar azimuth angle)"))
        outfile_source_wavelengths.write("%s %s\n" % (common_data['theta'], "# Theta (solar zenith angle)"))
        outfile_source_wavelengths.write("%s %s\n" % (common_data['CSR'], "# CSR value"))
        outfile_source_wavelengths.write("%s %s\n" % (common_data['freecad_file'], "# FreeCAD file"))
        outfile_source_wavelengths.write("%s %s\n" % (common_data['materials_file'], "# Materials file"))
        # np.savetxt(outfile_source_wavelengths, data_source_wavelength, fmt=['%f'])

    # --------- end

    # ---
    # Output source spectrum for calculation and total energy emitted
    # ---
    source_spectrum = otsun.spectrum_to_constant_step(common_data['data_file_spectrum'], 0.5, common_data['wavelength_ini'], common_data['wavelength_end'])
    energy_emitted = np.trapz(source_spectrum[:, 1], x=source_spectrum[:, 0])
    # --------- end

    light_source = otsun.LightSource(common_data['current_scene'], common_data['emitting_region'],
                                     1000.0, 1.0, common_data['direction_distribution'],common_data['polarization_vector'])
    # ---
    # Outputs for thermal absorber materials (Th) in Spectral Analysis
    # ---
    if captured_energy_Th > 1E-9:
        data_Th_points_absorber = np.array(np.concatenate(Th_points_absorber))
        table_Th = otsun.make_histogram_from_experiment_results(
            Th_wavelength, Th_energy, common_data['wavelength_step'], common_data['aperture_collector_Th'],
            light_source.emitting_region.aperture)
        table_Th_05 = otsun.twoD_array_to_constant_step(table_Th, 0.5, common_data['wavelength_ini'], common_data['wavelength_end'])
        spectrum_by_table_Th_05 = source_spectrum[:, 1] * table_Th_05[:, 1]
        power_absorbed_from_source_Th = np.trapz(spectrum_by_table_Th_05, x=source_spectrum[:, 0])
        efficiency_from_source_Th = power_absorbed_from_source_Th / energy_emitted

        np.savetxt(
            os.path.join(common_data['destfolder'], 'Th_spectral_efficiency.txt'),
            table_Th,
            fmt=['%f', '%f'],
            header="wavelength(nm) efficiency_Th_absorbed"
        )

        # with open(os.path.join(common_data['destfolder'], 'Th_spectral_efficiency.txt'), 'w') as outfile_Th_spectral:
        #     outfile_Th_spectral.write("%s\n" % ("#wavelength(nm) efficiency Th absorbed"))
        #     np.savetxt(outfile_Th_spectral, table_Th, fmt=['%f', '%f'])

        np.savetxt(
            os.path.join(common_data['destfolder'], 'Th_points_absorber.txt'),
            data_Th_points_absorber,
            fmt=['%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f'],
            header="energy_ray point_on_absorber[3] previous_point[3] normal_at_absorber_face[3] wavelength_ray(nm)"
        )

        # with open(os.path.join(common_data['destfolder'], 'Th_points_absorber.txt'), 'w') as outfile_Th_points_absorber:
        #     outfile_Th_points_absorber.write("%s\n" % (
        #         "#energy_ray point_on_absorber[3] previous_point[3] normal_at_absorber_face[3]"))
        #     np.savetxt(outfile_Th_points_absorber, data_Th_points_absorber,
        #                fmt=['%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f'])

        with open(os.path.join(common_data['destfolder'], 'Th_integral_spectrum.txt'), 'w') as outfile_Th_integral_spectrum:
            outfile_Th_integral_spectrum.write("%s\n" % (
                "#power_absorbed_from_source_Th irradiance_emitted(W/m2) efficiency_from_source_Th"))
            outfile_Th_integral_spectrum.write("%s %s %s\n" % (
                power_absorbed_from_source_Th * common_data['aperture_collector_Th'] * 1E-6,
                energy_emitted,
                efficiency_from_source_Th))
        # print power_absorbed_from_source_Th * aperture_collector_Th * 1E-6,
        # energy_emitted * exp.light_source.emitting_region.aperture * 1E-6, efficiency_from_source_Th

    # --------- end

    # ---
    # Outputs for photovoltaic materials (PV) in Spectral Analysis
    # ---
    if captured_energy_PV > 1E-9:
        data_PV_values = np.array(np.concatenate(PV_values))
        table_PV = otsun.make_histogram_from_experiment_results(PV_wavelength, PV_energy, common_data['wavelength_step'],
                                                                   common_data['aperture_collector_PV'],
                                                                   light_source.emitting_region.aperture)
        table_PV_05 = otsun.twoD_array_to_constant_step(table_PV, 0.5, common_data['wavelength_ini'], common_data['wavelength_end'])
        spectrum_by_table_PV_05 = source_spectrum[:, 1] * table_PV_05[:, 1]
        power_absorbed_from_source_PV = np.trapz(spectrum_by_table_PV_05, x=source_spectrum[:, 0])
        efficiency_from_source_PV = power_absorbed_from_source_PV / energy_emitted

        # iqe = internal_quantum_efficiency
        SR = otsun.spectral_response(table_PV_05, common_data['iqe'])
        ph_cu = otsun.photo_current(SR, source_spectrum)

        with open(os.path.join(common_data['destfolder'], 'PV_integral_spectrum.txt'), 'w') as outfile_PV_integral_spectrum:
            outfile_PV_integral_spectrum.write("%s\n" % (
                "#power_absorbed_from_source_PV irradiance_emitted(W/m2) efficiency_from_source_PV photocurrent(A/m2)"))
            outfile_PV_integral_spectrum.write("%s %s %s %s" % (
                power_absorbed_from_source_PV * common_data['aperture_collector_PV'] * 1E-6,
                energy_emitted, efficiency_from_source_PV, ph_cu
            ))
            outfile_PV_integral_spectrum.flush()

        np.savetxt(
            os.path.join(common_data['destfolder'], 'spectral_response_PV.txt'),
            SR, fmt=['%f', '%f'],
            header = "wavelength(nm) spectral_response(A/W)"
        )

        # with open(os.path.join(destfolder, 'spectral_response_PV-a.txt'), 'w') as outfile_spectral_response_PV:
        #     np.savetxt(outfile_spectral_response_PV, SR, fmt=['%f', '%f'])

        np.savetxt(
            os.path.join(common_data['destfolder'], 'PV_spectral_efficiency.txt'),
            table_PV, fmt=['%f', '%f'],
            header="wavelength(nm) efficiency_PV_absorbed"
        )

        # with open(os.path.join(common_data['destfolder'], 'PV_spectral_efficiency.txt'), 'w') as outfile_PV_spectral:
        #     outfile_PV_spectral.write("%s\n" % ("#wavelength(nm) efficiency_PV_absorbed"))
        #     np.savetxt(outfile_PV_spectral, table_PV, fmt=['%f', '%f'])

        np.savetxt(
            os.path.join(common_data['destfolder'], 'PV_paths_values.txt'),
            data_PV_values,
#            fmt=['%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%s'],
            fmt='%s',
            header="first_point_in_PV[3] second_point_in_PV[3] energy_ray_first_point energy_ray_second_point wavelength_ray(nm) absortion_coefficient_alpha(mm-1) incident_angle(deg.) material"
        )

        # with open(os.path.join(common_data['destfolder'], 'PV_paths_values.txt'), 'w') as outfile_PV_paths_values:
        #     outfile_PV_paths_values.write("%s\n" % (
        #         "#first_point_in_PV[3] second_point_in_PV[3] energy_ray_first_point energy_ray_second_point wavelength_ray(nm) absortion_coefficient_alpha(mm-1) incident_angle(deg.)"))
        #     np.savetxt(outfile_PV_paths_values, data_PV_values,
        #                fmt=['%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f'])


def compute(*args):
    w, common_data = args

    l_s = otsun.LightSource(common_data['current_scene'], common_data['emitting_region'],
                                     w, 1.0, common_data['direction_distribution'],common_data['polarization_vector'])

    exp = otsun.Experiment(common_data['current_scene'], l_s, common_data['number_of_rays'],
                           common_data['show_in_doc'])
    logger.info("launching experiment %s", [w, common_data['main_direction']])
    try:
        exp.run()
    except:
        logger.error("computation ended with an error")
        return
    common_data['data_consumer_queue'].put((
        w, exp.Th_energy, exp.Th_wavelength, exp.PV_energy, exp.PV_wavelength,
        exp.PV_values, exp.points_absorber_Th, exp.captured_energy_Th, exp.captured_energy_PV,
        exp.light_source.emitting_region.aperture * 0.001 * 0.001
    ))

    common_data['statuslogger'].increment()


def computation(data, root_folder):

    logger.info("experiment from spectral_analysis got called")

    common_data = {}

    manager = Manager()
    common_data['statuslogger'] = StatusLogger(manager, 0, root_folder)

    common_data['data_consumer_queue'] = Queue()

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

    #
    # Load parameters from user input
    #

    common_data['phi'] = float(data['phi'])
    common_data['theta'] = float(data['theta']) + 1E-9
    common_data['wavelength_ini'] = float(data['wavelength_ini'])
    common_data['wavelength_end'] = float(data['wavelength_end']) + 1E-4
    if data['wavelength_step'] == "":
        common_data['wavelength_step'] = 1.0
    else:
        common_data['wavelength_step'] = float(data['wavelength_step'])

    #
    # Prepare common data
    #

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

    doc = FreeCAD.openDocument(freecad_file)
    sel = doc.Objects

    common_data['current_scene'] = otsun.Scene(sel)

    common_data['show_in_doc'] = None

    common_data['number_of_rays'] = int(data['numrays'])

    if data['aperture_pv'] == "":
        common_data['aperture_collector_PV'] = 0
    else:
        common_data['aperture_collector_PV'] = float(data['aperture_pv'])
        common_data['iqe'] = 1
        if data.get('iqe_value', "") != "":
            common_data['iqe'] = float(data['iqe_value'])
        elif data.get('iqe_file', "") != "":
            common_data['iqe'] = os.path.join(files_folder, data['iqe_file'])

    if data['aperture_th'] == "":
        common_data['aperture_collector_Th'] = 0
    else:
        common_data['aperture_collector_Th'] = float(data['aperture_th'])

    common_data['move_elements'] = data.get('move_scene', 'no') == 'yes'

    common_data['polarization_vector'] = None

    common_data['main_direction'] = otsun.polar_to_cartesian(common_data['phi'], common_data['theta']) * -1.0  # Sun direction vector
    common_data['emitting_region'] = otsun.GeneralizedSunWindow(common_data['current_scene'], common_data['main_direction'])

    if common_data['move_elements']:
        tracking = otsun.MultiTracking(common_data['main_direction'], common_data['current_scene'])
        tracking.make_movements()

    #
    # Prepare computations
    #


    list_pars = []

    for w in np.arange(common_data['wavelength_ini'], common_data['wavelength_end'], common_data['wavelength_step']):
        list_pars.append((w, common_data))

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
    logger.info("Putting poison")
    common_data['data_consumer_queue'].put('kill')
    data_consumer_process.join()

    FreeCAD.closeDocument(doc.Name)


