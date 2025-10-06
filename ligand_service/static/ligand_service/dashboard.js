const refreshSpinner = document.getElementById('refreshSpinner');
const simsContainer = document.getElementById('simsContainer')
const selectedDirInfo = document.getElementById('filesInfo');
const confirmButton = document.getElementById("confirmButton");
const uploadStatusIndicator = document.getElementById("progressNumerical");
const inputTypeSelect = document.getElementById("inputTypeSelect");
const cancelButton = document.getElementById("cancelButton");
const browseButton = document.getElementById('browseButton');
const clearButton = document.getElementById('clearButton');
const queueAnalysisBtn = document.getElementById("queueAnalysisBtn");
const clearQueueAnalysisBtn = document.getElementById("clearQueueAnalysisBtn");
const historyContainer = document.getElementById("analysisHistoryContainer");

const analysisGroup = new Array();

async function updateSimsData() {
	animate_class = Array.from(refreshSpinner.classList).filter((c) => c.startsWith('animate'))[0];
	refreshSpinner.classList.remove(animate_class);
	void refreshSpinner.offsetWidth;
	await new Promise(r => setTimeout(r, 20));
	refreshSpinner.classList.add(animate_class);
	await new Promise(r => setTimeout(r, 50));
	let response = await fetch("api/sims-data", {});
	let newHTML = await response.text();
	if (simsContainer.innerHTML !== newHTML) {
		simsContainer.innerHTML = newHTML;
		prepareSimContainers();
		return
	}
	await new Promise(r => setTimeout(r, 50));
	response = await fetch("api/sims-data", {});
	newHTML = await response.text();
	if (simsContainer.innerHTML !== newHTML) {
		simsContainer.innerHTML = newHTML;
		prepareSimContainers();
	}
}


async function deleteSim(sim_name) {
	const response = fetch("api/sim/delete", {
		method: "POST",
		body: JSON.stringify({ sim_name: sim_name }),
	});
	await updateSimsData();
}


async function startSim(sim_name) {
	const response = fetch("api/sim/start", {
		method: "POST",
		body: JSON.stringify({ sim_name: sim_name }),
	});
	await updateSimsData();
}

function getSimName(any_inner_element) {
	console.log(any_inner_element)
	const simData = any_inner_element.closest('.sim-data');
	return simData.getElementsByClassName('sim-name')[0].innerText;
}


clearQueueAnalysisBtn.addEventListener("click", () => { analysisGroup.length = 0; updateAnalysisGroupDisplay() });

function updateAnalysisGroupDisplay() {
	const analysisGroupContainer = document.getElementById("analysisGroupContainer");
	console.log(analysisGroup)
	const analysisInfoTemplate = document.querySelector(".analysis-info.hidden")
	const emptyAnalysisInfo = document.querySelector(".empty-analysis-info.hidden")
	analysisGroupContainer.innerHTML = ""
	analysisGroup.forEach((x) => {
		const infoNode = analysisInfoTemplate.cloneNode();
		infoNode.classList.remove("hidden");
		infoNode.innerText = x.simName;
		analysisGroupContainer.appendChild(infoNode);
	});
	if (analysisGroupContainer.innerHTML == "") {
		const emptyAnalysisInfoNode = emptyAnalysisInfo.cloneNode(true);
		emptyAnalysisInfoNode.classList.remove("hidden");
		analysisGroupContainer.appendChild(emptyAnalysisInfoNode)
	}
}

queueAnalysisBtn.addEventListener('click', async (x) => {
	if (analysisGroup.length < 2) {
		return;
	}
	const response = fetch("api/group/start", {
		method: "POST",
		body: JSON.stringify({ sims: analysisGroup }),
	});
	analysisGroup.length = 0;
	updateAnalysisGroupDisplay();
	await updateHistoryData();
});


function prepareSimContainers() {
	const simContainers = document.getElementsByClassName("sim-data");

	Array.from(simContainers).forEach((x) => {
		const deleteBtn = x.getElementsByClassName('delete-sim-btn')[0];
		const simName = getSimName(deleteBtn);
		if (deleteBtn != null) {
			deleteBtn.addEventListener("click", () => {
				console.log('got event, requesting delete...');
				deleteSim(simName);
			});
		}

		const startSimBtn = x.getElementsByClassName('run-sim-btn')[0];
		if (startSimBtn != null) {
			startSimBtn.addEventListener("click", () => {
				console.log('got event, requesting start...');
				startSim(simName);
			});

		}

		const addToAnalysisBtn = x.getElementsByClassName('add-to-analysis-btn')[0];
		if (addToAnalysisBtn != null) {
			addToAnalysisBtn.addEventListener("click", () => {
				const seeResultNode = addToAnalysisBtn.parentNode.querySelector("a");
				const simId = seeResultNode.href.split("/").at(-1);
				for (const simInfo of analysisGroup) {
					if (simInfo.simId == simId) {
						console.log("Already on the list, skipping...")
						return
					}
				}
				analysisGroup.push({ "simName": simName, "simId": simId });
				updateAnalysisGroupDisplay();
			});
		}

	})
}


refreshSpinner.addEventListener("click", async (event) => {
	await updateSimsData();
});


var r = new Resumable({
	target: 'api/sim/upload',
	minFileSizeErrorCallback: function(file, errorCount) { },
	// testChunks: false,
	maxFilesErrorCallback: function(files, errorCount) {
		alert('Choose two files: topology and trajectory');
	},
	testChunks: false,
});


function getFileMainDirectory(file) {
	return file.relativePath.split('/')[0]
}

function displayCurrentFiles() {
	if (selectedInput === "topTrj") {
		selectedDirInfo.innerText = "Files: " + r.files.reduce((acc, val) => acc + " " + val.fileName, "");
	} else {
		selectedDirInfo.innerText = `Directory: ${getFileMainDirectory(r.files[0])}`;
	}

}

r.on('fileAdded', function(file, event) {
	// ensure that only one directory at most is present in the upload 
	if (selectedInput === "maestroDir") {
		console.log('Directory input, making sure oly one dir exists!')
		const fileMainDir = getFileMainDirectory(file)
		r.files = r.files.filter((file) => getFileMainDirectory(file) === fileMainDir)
	}

	displayCurrentFiles();
});

function resetResumableFileUploaderState() {
	selectedInput = inputTypeSelect.value;
	if (selectedInput === "topTrj") {
		selectedDirInfo.innerText = "Select files...";
		r.assignBrowse(browseButton, false);
		r.opts.maxFiles = 2
	} else {
		selectedDirInfo.innerText = "Select directory...";
		r.assignBrowse(browseButton, true);
		r.opts.maxFiles = undefined
	}
	r.files = []
}

r.on('complete', function(file, event) {
	uploadStatusIndicator.classList.add("hidden");
	confirmButton.classList.add("rounded-r-lg");
	selectedDirInfo.innerText = "Select directory...";
	resetResumableFileUploaderState();
	updateSimsData();
});

clearButton.addEventListener("click", () => {
	resetResumableFileUploaderState();
	r.cancel();
});

/*
r.on('filesAdded', function(arrayAdded, arraySkipped) {
	r.files = arrayAdded
	displayCurrentFiles();
});
*/

inputTypeSelect.addEventListener('change', (event) => {
	resetResumableFileUploaderState();
});

confirmButton.addEventListener("click", (event) => {
	const fileCount = r.files.length;
	if (fileCount <= 0) {
		return;
	}
	if (selectedInput === "topTrj") {
		if (fileCount < 2) {
			alert('Choose two files: topology and trajectory');
		}
	}

	uploadStatusIndicator.classList.remove("hidden");
	confirmButton.classList.remove("rounded-r-lg");

	r.opts.query = { 'fileCount': fileCount };
	// naming the directory
	if (selectedInput === "topTrj") {
		fileNames = [r.files[0].fileName, r.files[1].fileName].sort()
		dirName = fileNames[0] + "-" + fileNames[1]
		r.files.forEach((file) => { file.relativePath = `${dirName}/${file.fileName}` })
	}

	console.log('Starting upload!');
	r.upload();
});

r.on('progress', function(event) {
	uploadStatusIndicator.innerText = (r.progress() * 100).toPrecision(4) + "%";
});

async function deleteAnalysis(analysisContainer) {
	resultsId = analysisContainer.querySelector("a").href.split("/").at(-1)
	const response = fetch("api/group/delete", {
		method: "POST",
		body: JSON.stringify({ resultsId: resultsId }),
	});
	await updateHistoryData();
}


async function prepareAnalysisContainers() {
	const analysisContainers = document.getElementsByClassName("analysis-data");
	if (analysisContainers == null) {
		return;
	}
	const analysisContainerHeightClass = Array.from(analysisContainers[0].classList).filter((x) => String(x).startsWith("h-"))[0]
	const btnRotation = Array.from(analysisContainers[0].querySelector(".unfold-btn").classList).filter((x) => String(x).startsWith("rotate-"))[0]
	Array.from(analysisContainers).forEach(async (x) => {
		const deleteBtn = x.getElementsByClassName('delete-analysis-btn')[0];
		if (deleteBtn != null) {
			deleteBtn.addEventListener("click", () => {
				console.log('got event, requesting analysis delete...');
				deleteAnalysis(x);
				updateHistoryData();
			});
		}

		const unfoldBtn = x.getElementsByClassName('unfold-btn')[0];
		if (unfoldBtn != null) {
			unfoldBtn.addEventListener("click", () => {
				console.log('unfolding...');
				x.classList.toggle(analysisContainerHeightClass)
				unfoldBtn.classList.toggle(btnRotation)
			});
		}

	})
}


async function updateHistoryData() {
	await new Promise(r => setTimeout(r, 50));
	let response = await fetch("api/group/history", {});
	let newHTML = await response.text();
	if (historyContainer.innerHTML !== newHTML) {
		historyContainer.innerHTML = newHTML;
		prepareAnalysisContainers();
		return;
	}
	await new Promise(r => setTimeout(r, 50));
	response = await fetch("api/group/history", {});
	newHTML = await response.text();
	if (historyContainer.innerHTML !== newHTML) {
		historyContainer.innerHTML = newHTML;
		prepareAnalysisContainers();
	}
}

prepareSimContainers();
prepareAnalysisContainers();
resetResumableFileUploaderState();
setInterval(updateSimsData, 10000)
