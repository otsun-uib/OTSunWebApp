from otsunwebapp import app
import logging
import os

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
handler.setFormatter(formatter)
app.logger.addHandler(handler)
app.logger.setLevel(logging.DEBUG)

exp_logger = logging.getLogger("experiments")
exp_logger.addHandler(handler)
exp_logger.setLevel(logging.DEBUG)

app.config.from_mapping(
    APP_NAME=os.environ.get('APP_NAME', 'OTSunWebApp Local Server'),
    VERSION='0.7.6',
    UPLOAD_FOLDER='/tmp/otsunwebapp',
    MAIL_SENDER=os.environ.get('MAIL_SENDER'),
    MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
    MAIL_SERVER=os.environ.get('MAIL_SERVER'),
    MAIL_PASSWD=os.environ.get('MAIL_PASSWD'),
    MAIL_PORT=os.environ.get('MAIL_PORT')
)

HOST = "0.0.0.0"
PORT = int(os.environ.get('PORT', 7007))

app.logger.debug("Starting")
app.run(host=HOST, port=PORT, threaded=True)
