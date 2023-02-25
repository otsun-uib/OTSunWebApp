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
from shutil import copy
import zipfile
import dill
#import multiprocessing
import json

#logging.getLogger().setLevel(logging.DEBUG)
logger=logging.getLogger(__name__)

# finished_computations_counter = None
#
#
# def init_counter(args):
#     """ store the counter for later use """
#     global finished_computations_counter
#     finished_computations_counter = args

# def update_percentage(partial, total):
#     percentage = (100 * partial) / total
#     logger.debug('experiment is at %s percent', percentage)
#     data_status = {'percentage': percentage}
#     if partial == total:
#         data_status['status'] = 'finished'
#     else:
#         data_status['status'] = 'running'
#     with open(status_file, 'w') as fp:
#         json.dump(data_status, fp)


def compute(args):
    # get parameters
    ph, th, w, number_of_rays, aperture_collector = args
    logger.debug("running experiment2 with: ph=%s, th=%s, w=%s, rays=%s, aperture=%s",
                 ph, th, w, number_of_rays, aperture_collector)

    # prepare experiment
    main_direction = otsun.polar_to_cartesian(ph, th) * -1.0  # Sun direction vector
    emitting_region = otsun.SunWindow(current_scene, main_direction)
    l_s = otsun.LightSource(current_scene, emitting_region, w, 1.0, None)
    logger.debug("defining experiment")
    exp = otsun.Experiment(current_scene, l_s, number_of_rays, doc)

    # run experiment and compute output
    logger.debug("running experiment")
    exp.run(doc)
    logger.debug("experiment run")
    efficiency = (exp.captured_energy / aperture_collector) / (
            exp.number_of_rays / exp.light_source.emitting_region.aperture)
    doc.recompute()

    # update the number of finished computations
    # logger.debug("updating counters")
    # global finished_computations_counter
    # with finished_computations_counter.get_lock():
    #     logger.debug("got lock")
    #     finished_computations_counter.value += 1
    #     value = finished_computations_counter.value
    #     if (value == total_computations) or ((value % ((total_computations / 100)+1)) == 0):
    #         update_percentage(value, total_computations)
    #     logger.debug('finished %s of %s computations', value, total_computations)
    logger.debug("returning results")
    # return the results
    return (ph, th, w, efficiency, exp.PV_energy, exp.PV_wavelength, exp.PV_values)

def computation(data, root_folder):
    global current_scene
    global doc

    phi1 = float(data['phi1']) + 0.000001 #0 + 0.0000001 #
    theta1 = float(data['theta1']) + 0.000001 #0 + 0.0000001
    number_of_rays = int(data['numrays'])
    aperture_collector = 1. * 1. * 1.0 # TODO: What is this?
    lambda1 = float(data['lambda1']) # # 295.0
    files_folder = os.path.join(root_folder, 'files')
    freecad_file = os.path.join(files_folder, data['freecad_file'])
    materials_file = os.path.join(files_folder, data['materials_file'])
    with zipfile.ZipFile(materials_file) as z:
        for matfile in z.namelist():
            with z.open(matfile) as f:
                try:
                    mat = dill.load(f)
                    otsun.Material.by_name[mat.name] = mat
                except:
                    pass

    logger.debug("in experiment3", locals())

    FreeCAD.openDocument(freecad_file)
    doc = FreeCAD.ActiveDocument


    sel = doc.Objects
    current_scene = otsun.Scene(sel)

    # list_pars = []
    # for ph in np.arange(phi1, phi2, phidelta):
    #     for th in np.arange(theta1, theta2, thetadelta):
    #         for w in np.arange(lambda1, lambda2, lambdadelta):
    #             list_pars.append((ph, th, w, number_of_rays, aperture_collector))

    # finished_computations_counter = multiprocessing.Value('i', 0)
    # global total_computations
    # total_computations = len(list_pars)
    # global status_file
    status_file = os.path.join(root_folder, 'status.json')

    # Prepare pool of workers and feed it
    # logger.info("number of cpus: %s", multiprocessing.cpu_count())
    # pool = multiprocessing.Pool(initializer=init_counter, initargs=(finished_computations_counter,))

    data_status = {'status': 'running', 'percentage':'N/A'}
    with open(status_file, 'w') as fp:
        json.dump(data_status, fp)

    result = compute((phi1, theta1, lambda1, number_of_rays, aperture_collector),)

    data_status = {'status': 'finished', 'percentage':'100'}
    with open(status_file, 'w') as fp:
        json.dump(data_status, fp)

    # results = pool.map(compute, list_pars)
    # logger.debug('finisehd pool.map %s, %s', len(results), len(list_pars))
    destfolder = os.path.join(root_folder, 'output')
    try:
        os.makedirs(destfolder)
    except:
        pass # we suppose it already exists

    all_obj = doc.Objects
    for obj in all_obj:
        logger.debug('Object %s', obj.Name)

    doc.recompute()
    doc.saveAs(os.path.join(destfolder,'drawing.FCStd'))

    # Close document
    FreeCAD.closeDocument(doc.Name)

    # Process results
    Source_lambdas = []
    PV_energy = []
    PV_wavelength = []
    PV_values = []
    efficiencies = []

    # for result in results:
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
    with open(os.path.join(destfolder, 'kkk4.txt'), 'w') as outfile:
        outfile.write(str(result) + '\n')
    with open(os.path.join(destfolder, 'PV-10000-CAS4-kk.txt'), 'w') as outfile_PV:
        np.savetxt(outfile_PV, datacomp, fmt=['%f', '%f'])
    with open(os.path.join(destfolder, 'PV_values_1micro.txt'), 'w') as outfile_PV_values:
        np.savetxt(outfile_PV_values, data_PV_values)
    with open(os.path.join(destfolder, 'Source_lambdas_1micro.txt'), 'w') as outfile_Source_lambdas:
        outfile_Source_lambdas.write("%s %s" % (aperture_collector * 0.001 * 0.001,
                                                "# Collector aperture in m2") + '\n')
        outfile_Source_lambdas.write("%s %s" % (number_of_rays, "# Rays per wavelength") + '\n')
        np.savetxt(outfile_Source_lambdas, data_source_lambdas, fmt=['%f'])
    copy(freecad_file, destfolder)
    # Prepare zipfile
    #    shutil.make_archive(destfolder, 'zip', destfolder)
