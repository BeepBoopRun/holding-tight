`use strict`

const modalBackground = document.getElementById("modal-bg");
const modalView = document.getElementById("modal");
const modalGraphPlaceholder = document.getElementById("modal-graph");
const filenameInput = document.getElementById("graph-filename");
const filetypeInput = document.getElementById("graph-filetype");
const widthInput = document.getElementById("graph-width");
const heightInput = document.getElementById("graph-height");

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
	modalGraphPlaceholder.appendChild(graphToBorrow);
	await Plotly.Plots.resize(graphToBorrow);
	let width_resized = graphToBorrow._fullLayout.width;
	let height_resized = graphToBorrow._fullLayout.height;
	widthInput.value = width_resized;
	heightInput.value = height_resized;
	const prohibit_resize = {
		autosize: false
	};
	await Plotly.relayout(plotlyGraphBorrowed, prohibit_resize);
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


function makeGraphTransparent() {
	const layout = {
		paper_bgcolor: 'rgba(0,0,0,0)',
		plot_bgcolor: 'rgba(0,0,0,0)',
	};
	console.log(plotlyGraphBorrowed.layout);
	console.log(plotlyGraphBorrowed.layout.paper_bgcolor);
	console.log(plotlyGraphBorrowed.layout.plot_bgcolor);
	Plotly.relayout(plotlyGraphBorrowed, layout);
}

function downloadGraph() {
	console.log(filenameInput.value);
	console.log(filetypeInput.value);
	Plotly.downloadImage(plotlyGraphBorrowed, {
		format: filetypeInput.value,
		filename: filenameInput.value != "" ? filenameInput.value : "coral_graph",
	});
}

function changePlotWidth() {
	Plotly.relayout(plotlyGraphBorrowed, { width: Math.round(widthInput.value) })
}

function changePlotHeight() {
	Plotly.relayout(plotlyGraphBorrowed, { height: Math.round(heightInput.value) })
}

async function resizeGraph() {
	const allow_resize = {
		autosize: true
	};
	await Plotly.relayout(plotlyGraphBorrowed, allow_resize);
	let width_resized = plotlyGraphBorrowed._fullLayout.width;
	let height_resized = plotlyGraphBorrowed._fullLayout.height;
	widthInput.value = width_resized;
	heightInput.value = height_resized;

	const set_layout = {
		width: width_resized,
		height: height_resized,
		autosize: false,
	};
	await Plotly.relayout(plotlyGraphBorrowed, set_layout);
}

