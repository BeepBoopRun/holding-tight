FROM mambaorg/micromamba:2.3.0

USER root
RUN apt-get update && apt-get install git -y

COPY --chown=$MAMBA_USER:$MAMBA_USER . /home/$MAMBA_USER/prod
WORKDIR /home/$MAMBA_USER/prod

USER $MAMBA_USER
RUN micromamba install -y -n base -f ./env.yaml && \
    micromamba clean --all --yes

ENV ENV_NAME=base

RUN micromamba run python manage.py makeblastdb 
RUN micromamba run python manage.py migrate


CMD ["micromamba", "run", "sh", "docker_entrypoint.sh"]
