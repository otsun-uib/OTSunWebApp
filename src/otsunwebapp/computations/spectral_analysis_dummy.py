import logging
import sys
import os
sys.path.append("/usr/lib/freecad")
sys.path.append("/usr/lib/freecad/lib")
import FreeCAD
import otsun
import numpy as np
import multiprocessing
from otsunwebapp.utils.statuslogger import StatusLogger

logger = logging.getLogger(__name__)

def computation(data, root_folder):
    global doc
    global current_scene

    manager = multiprocessing.Manager()
    statuslogger = StatusLogger(manager, 0, root_folder)

    logger.info("experiment from spectral_analysis got called")
    _ROOT = os.path.abspath(os.path.dirname(__file__))
    data_file_spectrum = os.path.join(_ROOT, 'data', 'ASTMG173-direct.txt')
    destfolder = os.path.join(root_folder, 'output')
    try:
        os.makedirs(destfolder)
    except:
        pass  # we suppose it already exists

    show_in_doc = None
    polarization_vector = None
    phi = 0.0 + 1.E-9
    theta = 0.0 + 1.E-9
    wavelength_ini = 1000.0
    wavelength_end = 1000.0 + 1E-4
    wavelength_step = 1.0
    number_of_rays = 100

    aperture_collector_PV = 1000000
    aperture_collector_Th = 1000000

    direction_distribution = None


    files_folder = os.path.join(root_folder, 'files')
    freecad_file = os.path.join(files_folder, data['freecad_file'])
    materials_file = os.path.join(files_folder, data['materials_file'])

    otsun.Material.by_name = {}
    otsun.Material.load_from_json_zip(materials_file)
    doc = FreeCAD.openDocument(freecad_file)

    sel = doc.Objects
    current_scene = otsun.Scene(sel)

    manager = multiprocessing.Manager()
    statuslogger = StatusLogger(manager, 0, root_folder)

    captured_energy_pv = 0.0
    captured_energy_th = 0.0
    source_wavelength = []
    Th_energy = []
    Th_wavelength = []
    Th_points_absorber = []
    PV_energy = []
    PV_wavelength = []
    PV_values = []

    sel = doc.Objects
    current_scene = otsun.Scene(sel)

    number_of_runs = 0
    for _ in np.arange(wavelength_ini, wavelength_end, wavelength_step):
        number_of_runs += 1

    statuslogger.total = number_of_runs
    for w in np.arange(wavelength_ini, wavelength_end, wavelength_step):
        light_spectrum = w
        main_direction = otsun.polar_to_cartesian(phi, theta) * -1.0  # Sun direction vector
        emitting_region = otsun.SunWindow(current_scene, main_direction)
        l_s = otsun.LightSource(current_scene, emitting_region, light_spectrum, 1.0, direction_distribution,
                                   polarization_vector)
        exp = otsun.Experiment(current_scene, l_s, number_of_rays, show_in_doc)
        logger.info("launching experiment %s", [w, main_direction])
        try:
            exp.run()
        except:
            logger.error("computation ended with an error")
            continue
        Th_energy.append(exp.Th_energy)
        Th_wavelength.append(exp.Th_wavelength)
        PV_energy.append(exp.PV_energy)
        PV_wavelength.append(exp.PV_wavelength)
        source_wavelength.append(w)
        if exp.PV_values:
            PV_values.append(exp.PV_values)
        if exp.points_absorber_Th:
            Th_points_absorber.append(exp.points_absorber_Th)
        captured_energy_pv += exp.captured_energy_PV
        captured_energy_th += exp.captured_energy_Th

        statuslogger.increment()

    data_source_wavelength = np.array(source_wavelength)
    data_source_wavelength = data_source_wavelength.T
    source_wavelengths_file = os.path.join(destfolder, 'source_wavelengths.txt')
    with open(source_wavelengths_file, 'w') as outfile_source_wavelengths:
        outfile_source_wavelengths.write(
            "%s %s\n" % (aperture_collector_Th * 0.001 * 0.001, "# Collector Th aperture in m2"))
        outfile_source_wavelengths.write(
            "%s %s\n" % (aperture_collector_PV * 0.001 * 0.001, "# Collector PV aperture in m2"))
        outfile_source_wavelengths.write("%s %s\n" % (wavelength_ini, "# Wavelength initial in nm"))
        outfile_source_wavelengths.write("%s %s\n" % (wavelength_end, "# Wavelength final in nm"))
        outfile_source_wavelengths.write("%s %s\n" % (wavelength_step, "# Step of wavelength in nm"))
        outfile_source_wavelengths.write("%s %s\n" % (number_of_rays, "# Rays per wavelength"))


    source_spectrum = otsun.spectrum_to_constant_step(data_file_spectrum, 0.5, wavelength_ini, wavelength_end)
    energy_emitted = np.trapz(source_spectrum[:, 1], x=source_spectrum[:, 0])

    if captured_energy_th > 1E-9:
        data_Th_points_absorber = np.array(np.concatenate(Th_points_absorber))
        table_Th = otsun.make_histogram_from_experiment_results(Th_wavelength, Th_energy, wavelength_step,
                                                                   aperture_collector_Th,
                                                                   exp.light_source.emitting_region.aperture)
        table_Th_05 = otsun.twoD_array_to_constant_step(table_Th, 0.5, wavelength_ini, wavelength_end)
        spectrum_by_table_Th_05 = source_spectrum[:, 1] * table_Th_05[:, 1]
        power_absorbed_from_source_Th = np.trapz(spectrum_by_table_Th_05, x=source_spectrum[:, 0])
        efficiency_from_source_Th = power_absorbed_from_source_Th / energy_emitted

        with open(os.path.join(destfolder, 'Th_spectral_efficiency.txt'), 'w') as outfile_Th_spectral:
            outfile_Th_spectral.write("%s\n" % ("#wavelength(nm) efficiency Th absorbed"))
            np.savetxt(outfile_Th_spectral, table_Th, fmt=['%f', '%f'])

        with open(os.path.join(destfolder, 'Th_points_absorber.txt'), 'w') as outfile_Th_points_absorber:
            outfile_Th_points_absorber.write("%s\n" % (
                "#energy_ray point_on_absorber[3] previous_point[3] normal_at_absorber_face[3]"))
            np.savetxt(outfile_Th_points_absorber, data_Th_points_absorber,
                       fmt=['%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f'])

        with open(os.path.join(destfolder, 'Th_integral_spectrum.txt'), 'w') as outfile_Th_integral_spectrum:
            outfile_Th_integral_spectrum.write("%s\n" % (
                "#power_absorbed_from_source_Th irradiance_emitted(W/m2) efficiency_from_source_Th"))
            outfile_Th_integral_spectrum.write("%s %s %s\n" % (
                power_absorbed_from_source_Th * aperture_collector_Th * 1E-6,
                energy_emitted,
                efficiency_from_source_Th))

    if captured_energy_pv > 1E-9:
        data_PV_values = np.array(np.concatenate(PV_values))
        table_PV = otsun.make_histogram_from_experiment_results(PV_wavelength, PV_energy, wavelength_step,
                                                                   aperture_collector_PV,
                                                                   exp.light_source.emitting_region.aperture)
        table_PV_05 = otsun.twoD_array_to_constant_step(table_PV, 0.5, wavelength_ini, wavelength_end)
        spectrum_by_table_PV_05 = source_spectrum[:, 1] * table_PV_05[:, 1]
        power_absorbed_from_source_PV = np.trapz(spectrum_by_table_PV_05, x=source_spectrum[:, 0])
        efficiency_from_source_PV = power_absorbed_from_source_PV / energy_emitted

        with open(os.path.join(destfolder, 'PV_spectral_efficiency.txt'), 'w') as outfile_PV_spectral:
            outfile_PV_spectral.write("%s\n" % ("#wavelength(nm) efficiency_PV_absorbed"))
            np.savetxt(outfile_PV_spectral, table_PV, fmt=['%f', '%f'])

        with open(os.path.join(destfolder, 'PV_paths_values.txt'), 'w') as outfile_PV_paths_values:
            outfile_PV_paths_values.write("%s\n" % (
                "#first_point_in_PV[3] second_point_in_PV[3] energy_ray_first_point energy_ray_second_point wavelength_ray(nm) absortion_coefficient_alpha(mm-1) incident_angle(deg.)"))
            np.savetxt(outfile_PV_paths_values, data_PV_values,
                       fmt=['%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f'])

