`use strict`

const modalBackground = document.getElementById("modal-bg");
const modalView = document.getElementById("modal");

let plotlyGraphBorrowed = null;
let plotlyGraphBorrowedLayout = null;
let plotlyGraphOrigin = null;

function downloadFile(filename) {
	jobID = window.location.href.split("/").at(-1);
	request_url = `/download/${jobID}/${filename}`;
	const link = document.createElement("a");
	link.href = request_url;
	link.download = `coral_interactions.csv`;
	link.click();
}

function showContent(event) {
	const parent = event.target.closest('.content-window');
	const elem = parent.querySelector('.show-indicator');
	const infoElement = parent.querySelector('.info');
	infoElement.classList.toggle("hidden");
	elem.classList.toggle('rotate-270')
}

async function showPrintView(event) {
	event.stopPropagation()
	const graphOrigin = event.target.closest('.content-window').querySelector('.info');
	const graphToBorrow = graphOrigin.querySelector('.js-plotly-plot');
	plotlyGraphBorrowed = graphToBorrow;
	plotlyGraphOrigin = graphOrigin;
	const { width, height } = graphToBorrow._fullLayout;
	plotlyGraphBorrowedLayout = [width, height];
	modalView.classList.add("invisible");
	modalBackground.classList.remove("hidden");
	modalView.appendChild(graphToBorrow);
	await Plotly.Plots.resize(graphToBorrow);
	modalView.classList.remove("invisible");
	modalBackground.classList.remove("invisible");

}

async function bgClicked(event) {
	if (plotlyGraphBorrowed != null && plotlyGraphOrigin != null) {
		plotlyGraphOrigin.appendChild(plotlyGraphBorrowed);
		const set_layout = {
			width: plotlyGraphBorrowedLayout[0],
			height: plotlyGraphBorrowedLayout[1],
		};
		await Plotly.relayout(plotlyGraphBorrowed, set_layout);
		const allow_resize = {
			autosize: true
		};
		await Plotly.relayout(plotlyGraphBorrowed, allow_resize);
	}
	modalBackground.classList.add("hidden");
}


function modalClicked(event) {
	console.log("click on modal!");
	event.stopPropagation()
}

function handlePrintViewResize(event) {
	console.log("Resize request!");
}
