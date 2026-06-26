FROM python:3.6-slim

WORKDIR /app

RUN pip install --prefer-binary "scikit-learn<=0.22.1" "allensdk<=2.10.1" six
COPY mouse_connectivity_models/ /mouse_connectivity_models/
RUN pip install /mouse_connectivity_models --no-build-isolation

COPY build_sc.py knox_excluded.txt nathan_excluded.txt ./

# Ensure host cache dir exists before build (see build_container.sh)
COPY aba_cache/ /aba_cache/

VOLUME /output

ENTRYPOINT ["python", "/app/build_sc.py"]
