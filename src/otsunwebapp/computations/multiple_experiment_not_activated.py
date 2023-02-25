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


def compute(args):
    try:
        # get parameters
        ph, th, w, number_of_rays, aperture_collector, statuslogger = args
        logger.debug("running experiment2 with: ph=%s, th=%s, w=%s, rays=%s, aperture=%s",
                     ph, th, w, number_of_rays, aperture_collector)

        # prepare experiment
        main_direction = otsun.polar_to_cartesian(ph, th) * -1.0  # Sun direction vector
        emitting_region = otsun.SunWindow(current_scene, main_direction)
        l_s = otsun.LightSource(current_scene, emitting_region, w, 1.0, None)
        logger.debug("defining experiment")
        exp = otsun.Experiment(current_scene, l_s, number_of_rays)

        # run experiment and compute output
        logger.debug("running experiment")
        exp.run()
        logger.debug("experiment run")
        efficiency = (exp.captured_energy / aperture_collector) / (
                exp.number_of_rays / exp.light_source.emitting_region.aperture)

        # update the number of finished computations
        logger.debug("updating counters")
        statuslogger.increment()
        logger.debug("returning results")
        # return the results
        return (ph, th, w, efficiency, exp.PV_energy, exp.PV_wavelength, exp.PV_values)
    except:
        logger.debug("Failed with parameters: %s", args)

def computation(data, root_folder):
    global current_scene
    #global doc

    manager = multiprocessing.Manager()
    statuslogger = StatusLogger(manager, 0, root_folder)

    phi1 = float(data['phi1']) + 0.000001 #0 + 0.0000001 #
    phi2 = float(data['phi2']) + 0.000001 #0
    phidelta = float(data['phidelta']) #0.1
    theta1 = float(data['theta1']) + 0.000001 #0 + 0.0000001
    theta2 = float(data['theta2']) + 0.000001 #0
    thetadelta = float(data['thetadelta']) #0.1
    number_of_rays = int(data['numrays'])
    aperture_collector = 1. * 1. * 1.0 # TODO: What is this?
    lambda1 = float(data['lambda1']) # # 295.0
    lambda2 = float(data['lambda2']) # # 810.5
    lambdadelta = float(data['lambdadelta']) # # 0.5
    files_folder = os.path.join(root_folder, 'files')
    freecad_file = os.path.join(files_folder, data['freecad_file'])
    materials_file = os.path.join(files_folder, data['materials_file'])

    otsun.Material.load_from_zipfile(materials_file)

    logger.debug("in experiment2", locals())

    FreeCAD.openDocument(freecad_file)
    doc = FreeCAD.ActiveDocument


    sel = doc.Objects
    current_scene = otsun.Scene(sel)


    list_pars = []
    for ph in np.arange(phi1, phi2, phidelta):
        for th in np.arange(theta1, theta2, thetadelta):
            for w in np.arange(lambda1, lambda2, lambdadelta):
                list_pars.append((ph, th, w, number_of_rays, aperture_collector, statuslogger))

    statuslogger.total = len(list_pars)

    # Prepare pool of workers and feed it
    logger.info("number of cpus: %s", multiprocessing.cpu_count())
    pool = multiprocessing.Pool()
    results = pool.map(compute, list_pars)
    logger.debug('finisehd pool.map %s, %s', len(results), len(list_pars))

    # Close document
    FreeCAD.closeDocument(doc.Name)

    # Process results
    Source_lambdas = []
    PV_energy = []
    PV_wavelength = []
    PV_values = []
    efficiencies = []

    for result in results:
        (ph, th, w, efficiency, pv_energy, pv_wavelength, pv_values) = result
        PV_energy.append(pv_energy)
        PV_wavelength.append(pv_wavelength)
        PV_values.append(pv_values)
        Source_lambdas.append(w)

    xarray = np.array(np.concatenate(PV_energy))
    yarray = np.array(np.concatenate(PV_wavelength))
    datacomp = np.array([xarray, yarray])
    datacomp = datacomp.T
    data_PV_values = np.array(np.concatenate(PV_values))
    data_source_lambdas = np.array(Source_lambdas)

    # Write files with output
    destfolder = os.path.join(root_folder, 'output')
    os.makedirs(destfolder)
    with open(os.path.join(destfolder, 'kkk4.txt'), 'w') as outfile:
        for result in results:
            outfile.write(str(result) + '\n')
    with open(os.path.join(destfolder, 'PV-10000-CAS4-kk.txt'), 'w') as outfile_PV:
        np.savetxt(outfile_PV, datacomp, fmt=['%f', '%f'])
    with open(os.path.join(destfolder, 'PV_values_1micro.txt'), 'w') as outfile_PV_values:
        np.savetxt(outfile_PV_values, data_PV_values) #,
                   #fmt=['%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f', '%f'])
    with open(os.path.join(destfolder, 'Source_lambdas_1micro.txt'), 'w') as outfile_Source_lambdas:
        outfile_Source_lambdas.write("%s %s" % (aperture_collector * 0.001 * 0.001,
                                                "# Collector aperture in m2") + '\n')
        outfile_Source_lambdas.write("%s %s" % (number_of_rays, "# Rays per wavelength") + '\n')
        outfile_Source_lambdas.write("%s %s" % (lambdadelta, "# Step of wavelength in nm") + '\n')
        np.savetxt(outfile_Source_lambdas, data_source_lambdas, fmt=['%f'])
    # Prepare zipfile
    #    shutil.make_archive(destfolder, 'zip', destfolder)
