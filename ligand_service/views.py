from pathlib import Path
from time import sleep
import uuid
import json
import logging
import shutil

from django.http import HttpResponse, HttpResponseRedirect
from django.http.response import HttpResponseBadRequest
from django.shortcuts import render
from django.conf import settings
from django.http import FileResponse, Http404
from django.template.loader import render_to_string

from ligand_service.contacts import get_trajectory_frame_count
from ligand_service.utils import (
    ResumableFilesManager,
    get_user_uploads_dir,
    get_user_work_dir,
    get_user_results_dir,
)

from .models import GroupAnalysis, Simulation
from . import tasks

logger = logging.getLogger(__name__)
file_manager = ResumableFilesManager()


def start_sim_task(sim: Simulation, session_key: str):
    if sim.is_not_queued():
        files = sim.get_trajectory_files()
        print("Starting simulation!", flush=True)
        if files is None:
            return HttpResponse()
        print("Files are not None!", flush=True)
        sim.analysis_task_id = tasks.start_simulation(
            files.topology,
            files.trajectory,
            get_user_work_dir(session_key) / sim.dirname,
            get_user_results_dir(sim.results_id),
        ).id
        sim.save()


def start_sim(request):
    sim_name = json.loads(request.body)["sim_name"]
    session_key = request.session.session_key
    sim = Simulation.objects.get(user_key=session_key, dirname=sim_name)
    start_sim_task(sim, session_key)
    return HttpResponse()


def upload_sim(request):
    if not request.session.session_key:
        request.session.create()
    if request.method == "POST":
        _, dir_complete = file_manager.handle_resumable_post_request(
            request.POST,
            request.FILES.get("file", None),
            get_user_uploads_dir(request.session.session_key),
        )
        if dir_complete is not None:
            print("Adding new simulation file!", flush=True)
            try:
                sim = Simulation.objects.create(
                    dirname=dir_complete.name,
                    user_key=request.session.session_key,
                )
                sim.save()
                start_sim_task(sim, request.session.session_key)
            except Exception as e:
                print(f"Db error: {e}")

    elif request.method == "GET":
        has_chunk, dir_complete = file_manager.handle_resumable_get_request(
            request.GET, get_user_uploads_dir(request.session.session_key)
        )
        if dir_complete:
            try:
                potential_existing = Simulation.objects.filter(
                    dirname=dir_complete.name,
                    user_key=request.session.session_key,
                )
                if not potential_existing:
                    Simulation.objects.create(
                        dirname=dir_complete.name,
                        user_key=request.session.session_key,
                    ).save()
            except Exception as e:
                print(f"Db error: {e}")
        if has_chunk:
            return HttpResponse(status=200)
        else:
            return HttpResponse(status=204)
    return HttpResponse(status=200)


def delete_sim(request):
    sim_name = json.loads(request.body)["sim_name"]
    sim = Simulation.objects.get(user_key=request.session.session_key, dirname=sim_name)
    sim.delete()
    session_key = request.session.session_key
    shutil.rmtree(get_user_uploads_dir(session_key) / sim.dirname, ignore_errors=True)
    shutil.rmtree(get_user_work_dir(session_key) / sim.dirname, ignore_errors=True)
    shutil.rmtree(get_user_results_dir(str(sim.results_id)), ignore_errors=True)
    return HttpResponse()


def send_sims_data(request):
    sims = Simulation.objects.filter(user_key=request.session.session_key)

    for sim in sims:
        print("SIM STATUS")
        print("NOT QUEUED: ", sim.is_not_queued())
        print("RUNNING: ", sim.is_running())
        print("FINISHED: ", sim.is_finished())
        print("FAILED: ", sim.has_failed())
        print("---", flush=True)

    sims_data = render_to_string("submit/sims_data.html", {"user_dirs": sims})
    headers = {
        "Content-Type": "text/html; charset=utf-8",
    }
    return HttpResponse(sims_data, headers=headers)


def send_analyses_history(request):
    sims_data = render_to_string(
        "submit/history.html",
        {"history": GroupAnalysis.objects.filter(user_key=request.session.session_key)},
    )
    headers = {
        "Content-Type": "text/html; charset=utf-8",
    }
    return HttpResponse(sims_data, headers=headers)


def run_group_analysis(request):
    sims_group = json.loads(request.body)["sims"]
    exp_data = json.loads(request.body)["expData"]

    print("PRINTING SIM DATA")
    print(sims_group, flush=True)
    print(exp_data, flush=True)

    used_sims = []
    for sim_info in sims_group:
        sim_id = sim_info["simId"]
        sim = Simulation.objects.get(
            results_id=sim_id, user_key=request.session.session_key
        )
        if sim:
            used_sims.append(sim)

    results_dirs = [get_user_results_dir(sim.results_id) for sim in used_sims]

    tasks.analyse_group(results_dirs)
    print("Creating a group analysis:", used_sims, flush=True)
    analysis = GroupAnalysis.objects.create(
        user_key=request.session.session_key,
    )
    analysis.sims.set(used_sims)
    group_result_id = analysis.results_id

    for idx, result_dir in enumerate(results_dirs):
        data = {"Simulation name": sims_group[idx]["simName"]}
        for key in exp_data.keys():
            split = key.split(",")
            if len(split) == 1:
                print("Got value name key", exp_data[key])
            elif len(split) == 3:
                print("Got value", exp_data[split])
        with open(result_dir / "exp_data.json", "w") as f:
            pass
    print("Created analysis:", analysis)

    return HttpResponse()


def delete_group_analysis(request):
    results_id = json.loads(request.body)["resultsId"]
    print("DELETING:", results_id, flush=True)
    GroupAnalysis.objects.get(
        user_key=request.session.session_key, results_id=results_id
    ).delete()
    return HttpResponse()


def dashboard(request):
    return render(
        request,
        "submit/dashboard.html",
        {
            "user_dirs": Simulation.objects.filter(
                user_key=request.session.session_key
            ),
            "history": GroupAnalysis.objects.filter(
                user_key=request.session.session_key
            ),
        },
    )


def redirect_to_dashboard(request):
    return HttpResponseRedirect("/dashboard")


def render_about(request):
    return render(request, "about.html")


def example_submission(request):
    return render(request, "example_submission.html")


def show(request, sim_id):
    print("GOT SIM_ID:", sim_id)
    for sim in Simulation.objects.all():
        print(sim.results_id)
    print("--", flush=True)
    sim_results_dir = get_user_results_dir(sim_id)
    if not sim_results_dir.is_dir():
        return HttpResponseRedirect("/dashboard/")
    with open(get_user_results_dir(sim_id) / "run_data.json") as f:
        run_data = json.load(f)
    return render(
        request,
        "search/results.html",
        {
            "run": run_data,
        },
    )


def download_file(request, filepath):
    filepath = Path("./user_uploads/" + filepath)
    if filepath.is_file():
        return FileResponse(
            open(filepath, "rb"), as_attachment=True, filename=filepath.name
        )
    else:
        raise Http404("File does not exist")
