FROM python:3.10

WORKDIR /opt
COPY requirement.txt /opt/
RUN python -m pip install -r requirement.txt
RUN python -m pip install google-generativeai

EXPOSE 9405

COPY src /opt/src
COPY app.py config.yml /opt/

CMD python -u app.py \
    --host ${HOST} \
    --port ${PORT} \
    --workers ${WORKERS}