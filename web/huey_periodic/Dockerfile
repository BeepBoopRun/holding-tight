FROM mambaorg/micromamba:2.3.0

USER $MAMBA_USER
RUN id

WORKDIR /home/$MAMBA_USER/prod

COPY --chown=$MAMBA_USER:$MAMBA_USER ./env.yaml env.yaml

RUN micromamba install -y -n base -f ./env.yaml && \
    micromamba clean --all --yes

COPY --chown=$MAMBA_USER:$MAMBA_USER ./setup ./setup
RUN micromamba run python /home/$MAMBA_USER/prod/setup/makeblastdb.py
RUN micromamba run python /home/$MAMBA_USER/prod/setup/getchebi.py 

COPY --chown=$MAMBA_USER:$MAMBA_USER ./ligand_service ./ligand_service
COPY --chown=$MAMBA_USER:$MAMBA_USER ./theme ./theme
COPY --chown=$MAMBA_USER:$MAMBA_USER ./manage.py .
COPY --chown=$MAMBA_USER:$MAMBA_USER ./example_results ./example_results

ENV ENV_NAME=base
ENV PYTHONUNBUFFERED=1
ENV RUNNING_IN_DOCKER=True
