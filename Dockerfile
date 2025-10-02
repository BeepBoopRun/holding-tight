FROM mambaorg/micromamba:2.3.0

USER root
RUN apt-get update && apt-get install curl -y
RUN mkdir -p /home/$MAMBA_USER/prod/user_uploads
RUN mkdir -p /var/log/django/
RUN mkdir -p /var/log/huey/
RUN chown -R 57439:57439 /home/$MAMBA_USER
RUN mkdir -p /var/log/django /var/log/huey \
    && chown -R 57439:57439 /var/log/django /var/log/huey

USER $MAMBA_USER
RUN id
ENV NVM_DIR=/home/$MAMBA_USER/.nvm
RUN mkdir -p $NVM_DIR \
    && curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash \
    && . "$HOME/.nvm/nvm.sh" \
    && nvm install v22.19.0 \
    && nvm which node \
    && node -v \
    && npm -v
ENV PATH=$NVM_DIR/versions/node/v22.19.0/bin/:$PATH

WORKDIR /home/$MAMBA_USER/prod

COPY --chown=$MAMBA_USER:$MAMBA_USER ./env.yaml env.yaml

RUN micromamba install -y -n base -f ./env.yaml && \
    micromamba clean --all --yes

COPY --chown=$MAMBA_USER:$MAMBA_USER ./setup ./setup
RUN micromamba run python /home/$MAMBA_USER/prod/setup/makeblastdb.py
RUN micromamba run python /home/$MAMBA_USER/prod/setup/getchebi.py 

COPY --chown=$MAMBA_USER:$MAMBA_USER . .
ENV ENV_NAME=base
ENV PYTHONUNBUFFERED=1
ENV RUNNING_IN_DOCKER=True


CMD ["micromamba", "run", "sh", "docker_entrypoint.sh"]
