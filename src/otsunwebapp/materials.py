import logging
import sys
import os
import tempfile
from uuid import uuid4
from textwrap import dedent

sys.path.append("/usr/lib/freecad")
sys.path.append("/usr/lib/freecad/lib")
import otsun
# import dill

# import dummy.default_settings
# UPLOAD_FOLDER = "/tmp/" # dummy.default_settings.UPLOAD_FOLDER
# TODO: customize
#config = os.environ.get('OTSUN_CONFIG_FILE')
#if config:
#    execfile(config)

logger = logging.getLogger(__name__)

# if not os.path.exists(UPLOAD_FOLDER):
#     logger.info('creating upload folder')
#     os.makedirs(UPLOAD_FOLDER)
# else:
#     if not os.access(UPLOAD_FOLDER, os.W_OK):
#         UPLOAD_FOLDER += str(uuid4())
#         os.makedirs(UPLOAD_FOLDER)


def create_material(data, files, folder):
    logger.debug(data)
    kind_of_material = data['kind_of_material']
    with tempfile.TemporaryDirectory() as tempfolder:
        if kind_of_material != 'two_layers_material':
            filenames = {}
            for file_id in files:
                fs = files[file_id]
                if fs.filename == '':
                    continue
                fn = os.path.join(tempfolder, fs.filename)
                fs.save(fn)
                filenames[file_id] = fn
            files = filenames

        if kind_of_material == 'constant_ior':
            otsun.SimpleVolumeMaterial(data['name'],
                                       float(data['ior']),
                                       None if data['at_co'] == '' else float(data['at_co']))
        elif kind_of_material == 'variable_ior':
            otsun.WavelengthVolumeMaterial(data['name'], files['ior_file'])
        elif kind_of_material == 'PV_volume':
            otsun.PVMaterial(data['name'], files['PV_file'])
        elif kind_of_material == 'polarized_thin_film':
            if "back_file" in files:
                back_material = files['back_file']
            else:
                back_material = "Vacuum"
            if "front_file" in files:
                front_material = files['front_file']
            else:
                front_material = "Vacuum"
            otsun.PolarizedThinFilm(data['name'], files['thin_film_file'], front_material, back_material)
            # if data['front_vacuum']:
            #     if data['back_vacuum']:
            #         otsun.PolarizedThinFilm(data['name'], files['thin_film_file'],
            #                                 "Vacuum", "Vacuum")
            #     else:
            #         otsun.PolarizedThinFilm(data['name'], files['thin_film_file'],
            #                                 "Vacuum", files['back_file'])
            # else:
            #     if data['back_vacuum']:
            #         otsun.PolarizedThinFilm(data['name'], files['thin_film_file'],
            #                                 files['front_file'], "Vacuum")
            #     else:
            #         otsun.PolarizedThinFilm(data['name'], files['thin_film_file'],
            #                                 files['front_file'], files['back_file'])

        elif kind_of_material == 'opaque_simple_layer':
            otsun.OpaqueSimpleLayer(data['name'])
        elif kind_of_material == 'transparent_simple_layer':
            otsun.TransparentSimpleLayer(data['name'], float(data['pot']))
        elif kind_of_material == 'absorber_simple_layer':
            otsun.AbsorberSimpleLayer(data['name'], float(data['poa']))
        elif kind_of_material == 'absorber_lambertian_layer':
            otsun.AbsorberLambertianLayer(data['name'], float(data['poa']),
                                          float(data['weight']), data['kind'])
        elif kind_of_material == 'absorber_TW_model_layer':
            otsun.AbsorberTWModelLayer(data['name'],
                                       float(data['poa']),
                                       float(data['b_constant']),
                                       float(data['c_constant']))
        elif kind_of_material == 'reflector_specular_layer':
            otsun.ReflectorSpecularLayer(data['name'],
                                         float(data['por']),
                                         None if data['sigma_1'] == '' else float(data['sigma_1']),
                                         None if data['sigma_2'] == '' else float(data['sigma_2']),
                                         None if data['k'] == '' else float(data['k']))
        elif kind_of_material == 'reflector_lambertian_layer':
            otsun.ReflectorLambertianLayer(data['name'], float(data['por']),
                                           float(data['weight']), data['kind'])
        elif kind_of_material == 'metallic_specular_layer':
            otsun.MetallicSpecularLayer(data['name'],
                                        files['ior_file'],
                                        None if data['sigma_1'] == '' else float(data['sigma_1']),
                                        None if data['sigma_2'] == '' else float(data['sigma_2']),
                                        None if data['k'] == '' else float(data['k']))
        elif kind_of_material == 'metallic_lambertian_layer':
            otsun.MetallicLambertianLayer(data['name'], files['ior_file'],
                                          float(data['weight']), data['kind'])
        elif kind_of_material == 'polarized_coating_reflector_layer':
            otsun.PolarizedCoatingReflectorLayer(data['name'],
                                                 files['coating_file'],
                                                 None if data['sigma_1'] == '' else float(data['sigma_1']),
                                                 None if data['sigma_2'] == '' else float(data['sigma_2']),
                                                 None if data['k'] == '' else float(data['k']))
        elif kind_of_material == 'polarized_coating_transparent_layer':
            otsun.PolarizedCoatingTransparentLayer(data['name'], files['coating_file'])
        elif kind_of_material == 'polarized_coating_absorber_layer':
            otsun.PolarizedCoatingAbsorberLayer(data['name'], files['coating_file'])
        elif kind_of_material == 'two_layers_material':
            name = data['name']
            mat_front_name = data['name_front']
            mat_back_name = data['name_back']
            filename = os.path.join(folder, data['name'] + '.otmaterial')
            json_content = f'''\
                {{
                    "name": "{name}",
                    "classname": "TwoLayerMaterial",
                    "name_front_layer": "{mat_front_name}",
                    "name_back_layer": "{mat_back_name}"
                }}'''
            with open(filename, 'w') as f:
                f.write(dedent(json_content))
            return filename
            # otsun.TwoLayerMaterial(data['name'], mat_front_name, mat_back_name)
        elif kind_of_material == 'simple_symmetric_surface':
            otsun.ReflectorLambertianLayer("rlamb", float(data['por']))
            otsun.TwoLayerMaterial(data['name'], "rlamb", "rlamb")
        elif kind_of_material == 'simple_absorber_surface':
            otsun.AbsorberSimpleLayer(data['name'], 1 - float(data['poa']))
        material = otsun.Material.by_name[data['name']]
        # temp_folder = os.path.join(folder, str(uuid4()))
        # os.makedirs(temp_folder)
        # filename = os.path.join(temp_folder, data['name'] + '.rtmaterial')
        # filename = '/tmp/'+data['name']+'.rtmaterial'
        # with open(filename, 'wb') as f:
        #     dill.dump(material, f)
        filename = os.path.join(folder, data['name'] + '.otmaterial')
        material.save_to_json_file(filename)
        return filename
