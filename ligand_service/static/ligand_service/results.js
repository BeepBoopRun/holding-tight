`use strict`

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
function showPrintView(event) {
	console.log("Showing print view!");
	event.stopPropagation()
}
