const refreshSpinner = document.getElementById('refreshSpinner');
const simsContainer = document.getElementById('simsContainer')
const selectedDirInfo = document.getElementById('filesInfo');
const confirmButton = document.getElementById("confirmButton");
const uploadStatusIndicator = document.getElementById("progressNumerical");
const inputTypeSelect = document.getElementById("inputTypeSelect");
const cancelButton = document.getElementById("cancelButton");
const browseButton = document.getElementById('browseButton');
const clearButton = document.getElementById('clearButton');


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

function getSimName(any_inner_element) {
	const simData = any_inner_element.closest('.sim-data');
	return simData.getElementsByClassName('sim-name')[0].innerText;
}

function prepareSimContainers() {
	const simContainers = document.getElementsByClassName("sim-data");

	Array.from(simContainers).forEach((x) => {
		const deleteBtn = x.getElementsByClassName('delete-sim-btn')[0];
		console.log(deleteBtn);
		const simName = getSimName(deleteBtn);
		deleteBtn.addEventListener("click", () => {
			console.log('got event, requesting delete...');
			deleteSim(simName);
		});
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
});

function displayCurrentFiles() {
	if (selectedInput === "topTrj") {
		selectedDirInfo.innerText = "Files: " + r.files.reduce((acc, val) => acc + " " + val.fileName, "");
	} else {
		selectedDirInfo.innerText = `Directory: ${r.files[0].relativePath.split('/')[0]}`;
	}

}

r.on('fileAdded', function(file, event) {
	console.log("Single file", file)
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
	uploadStatusIndicator.classList.remove("hidden");
	confirmButton.classList.remove("rounded-r-lg");
	r.opts.query = { 'fileCount': fileCount };
	console.log('Starting upload!');
	r.upload();
});

r.on('progress', function(event) {
	uploadStatusIndicator.innerText = (r.progress() * 100).toPrecision(4) + "%";
});



prepareSimContainers();
resetResumableFileUploaderState();
