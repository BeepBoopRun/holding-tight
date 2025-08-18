FROM mambaorg/micromamba:2.3.0

WORKDIR /prod

COPY --chown=$MAMBA_USER:$MAMBA_USER . .

USER $MAMBA_USER
RUN micromamba install -y -n base -f ./env.yaml && \
    micromamba clean --all --yes

CMD [ "sh", "docker_entrypoint.sh" ]
