FROM python:3.10

WORKDIR /opt
COPY requirement.txt /opt/
RUN python -m pip install -r requirement.txt
RUN python -m pip install google-generativeai

EXPOSE 9404

COPY src /opt/src
COPY app.py config.yml /opt/

CMD python -u app.py \
    --host ${HOST} \
    --port ${PORT} \
    --workers ${WORKERS} \
    --redis_host ${REDIS_HOST} \
    --redis_port ${REDIS_PORT} \
    --redis_password ${REDIS_PASSWORD} \
    --mysql_host ${MYSQL_HOST} \
    --mysql_port ${MYSQL_PORT} \
    --mysql_username ${MYSQL_USERNAME} \
    --mysql_password ${MYSQL_ROOT_PASSWORD} \
    --mysql_database ${MYSQL_DATABASE}