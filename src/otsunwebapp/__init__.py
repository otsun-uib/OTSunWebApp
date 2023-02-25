from __future__ import print_function

import importlib
from flask import Flask, request, render_template, send_from_directory, current_app, redirect, url_for
import flask
from uuid import uuid4
import os
import shutil
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import threading
from werkzeug.utils import secure_filename
# import processing_unit
# from processing_unit import run_experiment, run_processor
from .materials import create_material
import logging
from autologging import TRACE
import zipfile
import otsun


app = Flask(__name__, static_url_path='/static_file')
## app.config.from_object(otsunwebapp.default_settings)
## app.config.from_envvar("OTSUN_CONFIG_FILE", silent=True)
app.config.from_mapping(
    APP_NAME="OTSunWebApp Development",
    VERSION=None,
    OTSUN_VERSION=otsun.__version__,
    UPLOAD_FOLDER = '/tmp/OTSunDevelopmentServer',
    MAIL_SENDER = None,
    MAIL_SERVER = None,
    MAIL_USERNAME = None,
    MAIL_PASSWD = None,
    MAIL_PORT = None
)

UPLOAD_FOLDER = app.config['UPLOAD_FOLDER']
if not os.path.exists(UPLOAD_FOLDER):
    app.logger.info('creating upload folder')
    os.makedirs(UPLOAD_FOLDER)
else:
    if not os.access(UPLOAD_FOLDER, os.W_OK):
        UPLOAD_FOLDER += str(uuid4())
        os.makedirs(UPLOAD_FOLDER)
# endregion

# region Helper functions


def root_folder(identifier):
    """
    Returns the root folder where all files related to the given identifier are saved
    """
    folder = os.path.join(app.config['UPLOAD_FOLDER'], identifier)
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder


def files_folder(identifier):
    """
    Returns the folder where all files uploaded by the user and related to the given identifier are saved
    """
    folder = os.path.join(root_folder(identifier), 'files')
    if not os.path.exists(folder):
        os.makedirs(folder)
    return folder


def data_filename(identifier):
    """
    Returns the filename where the data associated with the identifier is stored
    """
    return os.path.join(root_folder(identifier), 'data.json')


def status_filename(identifier):
    """
    Returns the filename where the status of the computation associated with the identifier is stored
    """
    return os.path.join(root_folder(identifier), 'status.json')


def load_json(filename):
    """
    Loads a json file and returns its content as a dict

    Args:
        filename: str with the filename

    Returns:
        A dict with the contents of the file
    """
    try:
        with open(filename, 'r') as fp:
            saved_data = json.load(fp)
    except IOError:
        saved_data = {}
    return saved_data


def load_data(identifier):
    """
    Returns the contents of the data file associated with the identifier as a dict

    Args:
        identifier: str

    Returns:
        A dict with the data associated with the identifier
    """
    return load_json(data_filename(identifier))


def save_data(data, identifier):
    """
    Merges the data saved for the identifier with the given and saves it to disk.

    Args:
        data: dict with data to be merged
        identifier: str
    """
    saved_data = load_data(identifier)
    saved_data.update(data)
    with open(data_filename(identifier), 'w') as fp:
        json.dump(saved_data, fp)


def remove_from_data(identifier, key_to_delete):
    """
    Removes from the saved data the given key

    Args:
        identifier: str
        key_to_delete: str
    """
    saved_data = load_data(identifier)
    if key_to_delete in saved_data:
        del saved_data[key_to_delete]
        with open(data_filename(identifier), 'w') as fp:
            json.dump(saved_data, fp)


def save_file(the_file, identifier, filename):
    """
    Saves a file object to the files folder of an identifier

    Args:
        the_file: file object to be saved
        identifier: str
        filename: str with the name of the file to be saved
    """
    the_file.save(os.path.join(files_folder(identifier), filename))


def send_error_mail(identifier):
    app.logger.info("Sending mail for id %s", identifier)

    data = load_data(identifier)
    toaddr = data['email']

    if not app.config['MAIL_SENDER']:
        app.logger.info("Mail aborted... no server configured")
        return
    fromaddr = app.config['MAIL_SENDER']
    username = app.config['MAIL_USERNAME']
    passwd = app.config['MAIL_PASSWD']

    msg = MIMEMultipart()

    msg['From'] = fromaddr
    msg['To'] = toaddr
    msg['Subject'] = "Error in computation of %s" % app.config['APP_NAME']

    body = """\
    <html>
    <h2>Sorry! </h2>
      We found an error processing your request. Please contact the administrators at 
    <a href="%s">%s</a>,
      giving as reference the identifier:
    "%s"
    </html>
    """ % (app.config['MAIL_SENDER'],app.config['MAIL_SENDER'],identifier)

    msg.attach(MIMEText(body, 'html'))

    server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
    server.starttls()
    server.login(username, passwd)
    text = msg.as_string()
    server.sendmail(fromaddr, toaddr, text)
    server.quit()



def send_mail(toaddr, identifier):
    """
    Sends a mail with a link to the results of computation identified by identifier

    Uses global variables obtained from app.config to connect to smtp server

    Args:
        toaddr: str with the recipient
        identifier: str
    """
    app.logger.info("Sending mail for id %s", identifier)
    if not app.config['MAIL_SENDER']:
        app.logger.info("Mail aborted... no server configured")
        return
    fromaddr = app.config['MAIL_SENDER']
    username = app.config['MAIL_USERNAME']
    passwd = app.config['MAIL_PASSWD']

    data = load_data(identifier)
    results_url = data['results_url']

    msg = MIMEMultipart()

    msg['From'] = fromaddr
    msg['To'] = toaddr
    msg['Subject'] = "Results of computation of %s" % app.config['APP_NAME']

    body = """\
    <html>
    Get your results at:
    <a href="%s">link</a>
    </html>
    """ % (results_url)

    msg.attach(MIMEText(body, 'html'))

    server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
    server.starttls()
    server.login(username, passwd)
    text = msg.as_string()
    server.sendmail(fromaddr, toaddr, text)
    server.quit()


def make_zipfile(output_filename, source_dir):
    """
    Creates a zipfile from the contents of a folder

    Args:
        output_filename: str with full path where the zip file has to be written
        source_dir: str with full path of folder to be compressed
    """
    relroot = os.path.abspath(os.path.join(source_dir, os.pardir))
    with zipfile.ZipFile(output_filename, "w", zipfile.ZIP_DEFLATED) as myzip:
        for root, dirs, files in os.walk(source_dir):
            # add directory (needed for empty dirs)
            myzip.write(root, os.path.relpath(root, relroot))
            for thefile in files:
                filename = os.path.join(root, thefile)
                if os.path.isfile(filename):  # regular files only
                    arcname = os.path.join(os.path.relpath(root, relroot), thefile)
                    myzip.write(filename, arcname)

# endregion

# region Filter class


class FilterByThread(logging.Filter):
    def __init__(self, thread_id = None):
        super(FilterByThread, self).__init__()
        if not thread_id:
            thread_id = threading.current_thread().ident
        self.thread_id = thread_id

    def filter(self, record):
        return record.thread == self.thread_id

# endregion

# region Computation unit


def process_computation(identifier,
                        should_send_mail=True,
                        should_return_value=False,
                        loglevel=logging.INFO):
    try:
        dir_name = root_folder(identifier)
        data = load_data(identifier)
        computation_name = data.get('computation', None)
        if not computation_name:
            raise ValueError("No computation requested")
        try:
            module = importlib.import_module('.computations.'+computation_name, 'otsunwebapp')
            callable_computation = module.computation
        except (ImportError, AttributeError):
            raise ValueError('The computation is not implemented', computation_name)

        fh = logging.FileHandler(os.path.join(dir_name, "computations.log"))
        fh.setLevel(TRACE)
        formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(name)s %(funcName)s: %(message)s')
        fh.setFormatter(formatter)
        logfilter = FilterByThread()
        fh.addFilter(logfilter)

        app.logger.addHandler(fh)

        module_logger = logging.getLogger('otsunwebapp.computations.'+computation_name)
        module_logger.setLevel(loglevel)
        module_logger.addHandler(fh)

        otsun_logger = logging.getLogger('otsun')
        otsun_logger.setLevel(loglevel)
        otsun_logger.addHandler(fh)

        app.logger.info("otsun version is %s", otsun.__version__)

        app.logger.info("calling %s for %s from process %s",
                        computation_name,
                        data['identifier'],
                        os.getpid())
        result = callable_computation(data, dir_name)
        app.logger.info("computation finished for %s", data['identifier'])

        app.logger.removeHandler(fh)
        otsun_logger.removeHandler(fh)
        module_logger.removeHandler(fh)

        if should_send_mail:
            output_folder = os.path.join(dir_name, 'output')
            output_zip = os.path.join(dir_name, 'output.zip')
            make_zipfile(output_zip, output_folder)
            send_mail(toaddr=data['email'], identifier=identifier)
        if should_return_value:
            return result
    except Exception as e:
        app.logger.exception('Exception in main call to computation')
        send_error_mail(identifier)


# endregion

# region Processors for web calls


@app.before_request
def pre_prequest_logging():
    """
    Logs all calls to the app
    """
    app.logger.info("Got %s request of url %s from ip %s",
                    request.method,
                    request.url,
                    request.remote_addr)


@app.route('/')
def hello():
    """
    Root of the webapp. Redirects to the start page
    """
    return redirect(url_for('node', name='start'))


@app.route('/node/<name>/<identifier>', methods=['GET', 'POST'])
@app.route('/node/<name>', methods=['GET', 'POST'])
def node(name, identifier=None):
    """
    Processes the calls to the webapp.

    For GET posts, it creates an identifier (if it is not given)
    or loads the associated data (if it is given). Returns the rendered node

    For POST posts, it collects the data given by the form and saves the uploaded files.
    If there is a 'computation' in the data, it calls this computation.
    If there is a 'next_step' in the data, returns a redirection to this node; otherwise returns
    a redirection to the end page

    Args:
        name: str identifying the node of the webapp
        identifier: str

    Returns:
        html object or redirection
    """
    if request.method == 'GET':
        if identifier:
            data = load_data(identifier)
        else:
            data = {}
        return render_template(name + ".html", identifier=identifier, data=data)
    if request.method == 'POST':
        data = request.form.to_dict()
        if identifier is None:
            identifier = str(uuid4())
            data['identifier'] = identifier
        file_ids = request.files
        for file_id in file_ids:
            the_file = request.files[file_id]
            if the_file and the_file.filename != "":
                filename = the_file.filename
                filename = secure_filename(filename)
                app.logger.debug("filename is %s", filename)
                save_file(the_file, identifier, filename)
                data[file_id] = filename
        save_data(data, identifier)
        if 'computation_returns_data' in data:
            # new_data = process_processor(identifier)
            # data['computation'] = data['processor']
            # save_data(data, identifier)
            new_data = process_computation(identifier, False, True)
            save_data(new_data, identifier)
            remove_from_data(identifier, 'computation')
            remove_from_data(identifier, 'computation_returns_data')
        if 'next_step' in data:
            next_url = url_for('node', name=data['next_step'], identifier=identifier)
            return redirect(next_url)
        else:
            next_url = url_for('end_process', identifier=identifier)
            return redirect(next_url)


@app.route('/end/<identifier>')
def end_process(identifier):
    """
    Launches the computation and renders the end node of the webapp

    Remark: It creates a thread and launches the process_request in that thread.
    It makes the computation to be done asynchronously.

    Args:
        identifier:

    Returns:
        html object
    """
    data = {'results_url': url_for('send_file', identifier=identifier, _external=True)}
    save_data(data, identifier)

    app.logger.info("Launching thread for id %s from process %s",
                    identifier, os.getpid())
    # compute_thread = threading.Thread(target=process_experiment, args=(identifier,))
    compute_thread = threading.Thread(target=process_computation, args=(identifier,))
    compute_thread.start()
    return render_template("end.html", identifier=identifier)


@app.route('/status/<identifier>')
def status(identifier):
    """
    Renders the status page for the identifier if the status file exists;
    otherwise it renders an error page

    Args:
        identifier: str

    Returns:
        html object
    """
    data_status = load_json(status_filename(identifier))
    if not data_status:
        return render_template("error.html", identifier=identifier, sender=app.config['MAIL_SENDER'])
    return render_template("status.html", identifier=identifier, data_status=data_status)


@app.route('/results/<identifier>', methods=['GET'])
@app.route('/results/')
def send_file(identifier=None):
    """
    Sends the output of the computation in a zip file

    Args:
        identifier: str

    Returns:
        html object containing the file output.zip
    """
    if identifier is None:
        return "No process job specified"
    return send_from_directory(root_folder(identifier), 'output.zip', as_attachment=True)


@app.route('/static_file/<path:filename>')
def send_static_file(filename):
    """
    Sends and static file.

    Args:
        filename: str

    Returns:
        html object containing the file
    """
    return current_app.send_static_file(filename)
    #   send_from_directory(app.static_folder, filename)


@app.route('/material', methods=['GET', 'POST'])
def material():
    """
    Processes the node material of the webapp

    For GET requests, it redirects to the materials.html template
    For POST requests, it collects the data in the form, creates the material and
    returns a binary file containing it

    Remark: Uses create_material from materials.py

    Returns:

    """
    if request.method == 'GET':
        return render_template('materials.html')
    if request.method == 'POST':
        data = request.form.to_dict()
        app.logger.info("creating material with data: %s", data)
        files = request.files
        filename = create_material(data, files, app.config['UPLOAD_FOLDER'])
        return flask.send_file(filename, as_attachment=True)

# endregion

# region Functions for offline debugging


def run_offline(identifier):
    """
    Runs a computation offline (for testing and debugging purposes)

    It creates a copy of the data and files contained in the root directory to another one,
    and processes the request in this new copy.

    Args:
        identifier: str
    """
    root1 = root_folder(identifier)
    n = 1
    while os.path.exists(root1+'-'+str(n)):
        n += 1
    identifier2 = identifier+'-'+str(n)
    root2 = root1+'-'+str(n)
    os.makedirs(root2)
    shutil.copy(os.path.join(root1, 'data.json'), os.path.join(root2, 'data.json'))
    shutil.copytree(os.path.join(root1, 'files'), os.path.join(root2, 'files'))
    # process_experiment(identifier2, should_send_mail=False)
    process_computation(identifier2, should_send_mail=False, should_return_value=False, loglevel=TRACE)
    app.logger.info('Finished %s', identifier2)

# endregion

