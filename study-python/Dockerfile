FROM docker.m.daocloud.io/library/python:3.12-alpine
WORKDIR /srv
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple flask requests
COPY server.py /srv/server.py
EXPOSE 80
CMD ["python", "server.py"]
