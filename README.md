# OTSunWebApp

## Prerequisites

* docker and docker-compose must be installed

## Installation

* Download the repository to any folder

## Configuration

Copy the provided file `dotenv_sample` to `.env` and customize the variables:
* `CPU_COUNT`: Number of CPUs available for the container to run. Default: `4`
* `PORT`: Port where the server will run. Default: `8888`
* `MAIL_SERVER`: Address of the SMTP server to use for sending mails. If not given, the system will not send mails.
* `MAIL_PORT`: Port to connect, using TSL. Default: `587`
* `MAIL_SENDER`: Email address to show as sender of the messages
* `MAIL_USERNAME`: Username for the SMTP server
* `MAIL_PASSWD`: Password for the SMTP server

## Execution

* Open a terminal and navigate to the folder containing `docker-compose.yml`
* Run `docker-compose build`
* Run `docker-compose up`
* Open the page http://127.0.0.1:8888 (replace 8888 with the value given in `PORT` if necessary)