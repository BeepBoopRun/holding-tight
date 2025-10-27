`use strict`

const modalBackground = document.getElementById("modal-bg");
const modalView = document.getElementById("modal");

function downloadFile(filename) {
	jobID = window.location.href.split("/").at(-1);
	request_url = `/download/${jobID}/${filename}`;
	const link = document.createElement("a");
	link.href = request_url;
	link.download = `coral_interactions.csv`;
	link.click();
}

function showContent(event) {
	const elem = parent.querySelector('.show-indicator');
	const infoElement = parent.querySelector('.info');
	infoElement.classList.toggle("hidden");
	elem.classList.toggle('rotate-270')
}

function wait(ms) {
	return new Promise(resolve => setTimeout(resolve, ms));
}


async function showPrintView(event) {
	console.log("Showing print view!");
	const graphOrigin = event.target.closest('.content-window').querySelector('.info');
	const graphToBorrow = graphOrigin.querySelector('.js-plotly-plot');
	plotlyGraphBorrowed = graphToBorrow;
	plotlyGraphOrigin = graphOrigin;
	modalView.appendChild(graphToBorrow);
	modalBackground.classList.add("invisible");
	modalBackground.classList.remove("hidden");
	await Plotly.Plots.resize(graphToBorrow);
	modalBackground.classList.remove("invisible");

	event.stopPropagation()
}

async function bgClicked(event) {
	if (plotlyGraphBorrowed != null && plotlyGraphOrigin != null) {
		plotlyGraphOrigin.appendChild(plotlyGraphBorrowed);
		await Plotly.Plots.resize(plotlyGraphBorrowed);
	}
	modalBackground.classList.add("hidden");
}


function modalClicked(event) {
	console.log("click on modal!");
	event.stopPropagation()
}

