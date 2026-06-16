FROM mcr.microsoft.com/azurelinux/base/python:3.12 AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Microsoft ODBC Driver 18 for SQL Server (Azure Linux 3)
RUN ACCEPT_EULA=Y tdnf install -y unixODBC msodbcsql18 && tdnf clean all

WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app ./app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
