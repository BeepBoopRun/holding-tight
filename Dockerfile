FROM mambaorg/micromamba:2.3.0

RUN apt-get update && apt-get install wget

COPY --chown=$MAMBA_USER:$MAMBA_USER . /home/$MAMBA_USER/prod
WORKDIR /home/$MAMBA_USER/prod

USER $MAMBA_USER
RUN micromamba install -y -n base -f ./env.yaml && \
    micromamba clean --all --yes

RUN ./blast/prepare_blast.sh

CMD [ "sh", "docker_entrypoint.sh" ]
