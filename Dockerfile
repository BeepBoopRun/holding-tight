FROM mambaorg/micromamba:2.3.0

USER root
RUN apt-get update && apt-get install --no-install-recommends -y wget

COPY --chown=$MAMBA_USER:$MAMBA_USER . /home/$MAMBA_USER/prod
WORKDIR /home/$MAMBA_USER/prod

USER $MAMBA_USER
RUN micromamba install -y -n base -f ./env.yaml && \
    micromamba clean --all --yes

ENV ENV_NAME=base
RUN micromamba run ./blast/prepare_blast.sh

CMD ["micromamba", "run", "sh", "docker_entrypoint.sh"]
