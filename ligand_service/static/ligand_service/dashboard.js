const refreshSpinner = document.getElementById('refreshSpinner');
const simsContainer = document.getElementById('simsContainer')

async function updateSimsData() {
	const response = await fetch("api/sims-data", {});
	const newHTML = await response.text();
	animate_class = Array.from(refreshSpinner.classList).filter((c) => c.startsWith('animate'))[0];
	refreshSpinner.classList.remove(animate_class);
	void refreshSpinner.offsetWidth;
	simsContainer.innerHTML = newHTML;
	await new Promise(r => setTimeout(r, 20));
	refreshSpinner.classList.add(animate_class);
}


var r = new Resumable({
	target: 'api/sim/upload',
	minFileSizeErrorCallback: function(file, errorCount) { },
	// testChunks: false,
});

r.assignDrop(document.getElementById('browseButton'));
r.assignBrowse(document.getElementById('browseButton'), true);

const selectedDirInfo = document.getElementById('filesInfo');
r.on('fileAdded', function(file, event) {
	selectedDirInfo.innerText = `Directory: ${file.relativePath.split('/')[0]}`;
});

r.on('complete', function(file, event) {
	setTimeout(() => {
		updateSimsData();
	}, 10);
});

const confirmButton = document.getElementById("confirmButton");
const uploadStatusIndicator = document.getElementById("progressNumerical");
const progressInfoElem = document.getElementById("progressInfo");

r.on('progress', function(event) {
	uploadStatusIndicator.innerText = (r.progress() * 100).toPrecision(4) + "%";
});

confirmButton.addEventListener("click", (event) => {
	const fileCount = r.files.length;
	if (fileCount <= 0) {
		return
	}
	progressInfoElem.classList.remove("hidden");
	r.opts.query = { 'fileCount': fileCount };
	console.log('Starting upload!');
	r.upload();
});


const cancelButton = document.getElementById("")

function deleteSim(sim_name) {
	const response = fetch("api/sim/delete", {
		method: "POST",
		body: JSON.stringify({ sim_name: sim_name }),
	});
	updateSimsData();
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

prepareSimContainers();

refreshSpinner.addEventListener("click", async (event) => {
	updateSimsData();
	prepareSimContainers();
});
