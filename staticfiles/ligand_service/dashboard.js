function uploadThis(value) {
	resumables[value].upload();
	console.log("Started upload!");
}



window.addEventListener('DOMContentLoaded', () => {

	var r = new Resumable({
		target: 'api/file',
		minFileSizeErrorCallback: function(file, errorCount) { },
		// testChunks: false,
	});

	r.assignDrop(document.getElementById('browseButton'));
	r.assignBrowse(document.getElementById('browseButton'), true);
	r.on('fileAdded', function(file, event) {
		console.log(file)

	});
	const browseButton = document.getElementById("browseButton")
	const filesInfoElement = document.getElementById("filesInfo")
	const confirmButton = document.getElementById("confirmButton")
	const inputTypeSelect = document.getElementById("inputTypeSelect")
	const uploadStatusIndicator = document.getElementById("uploadStatus")
	r.on('progress', function() {
		uploadStatusIndicator.innerText = (r.progress() * 100).toPrecision(4) + "%"
		uploadStatusIndicator.classList.remove("invisible")
	});
	confirmButton.addEventListener("click", (event) => {
		const fileCount = resumables[0].files.length
		console.log(fileCount)
		resumables[0].opts.query = { 'fileCount': fileCount }
		console.log(resumables[0])
		resumables[0].upload()
	})

	function deleteSim(sim_name) {
		const response = fetch("https://example.org/post", {
			method: "POST",
			body: JSON.stringify({ sim_name: sim_name }),
		});
		// update sim_data
	}

	function getSimName(any_inner_element) {
		const simContainer = any_inner_element.closest('.sim-container')
		return simContainer.getElementsByClassName('sim-name')[0].innerText
	}

	function prepareSimContainers() {
		const simContainers = document.getElementsByClassName("sim-container")

		simContainers.forEach((x) => {
			const deleteBtn = x.getElementsByClassName('delete-sim-btn')[0];
			const simName = getSimName(deleteBtn)
			deleteBtn.addEventListener("click", () => {
				deleteSim(simName)
			});
		})
	}

});

let nextFileFormID = 1

function updateFormsetIDs(containingElement, newID) {
	const re = /submit-\d+|submit-__prefix__/
	const replaceText = `submit-${newID}`
	const allDescendants = containingElement.querySelectorAll("*")
	for (const desc of allDescendants) {
		if (desc.id) {
			desc.id = desc.id.replace(re, replaceText)
		}
		if (desc.htmlFor) {
			desc.htmlFor = desc.htmlFor.replace(re, replaceText)
		}
		if (desc.name) {
			desc.name = desc.name.replace(re, replaceText)
		}
	}
}

function addFiles() {
	const template = document.getElementById('file-input-template');
	const form = document.getElementById('file-table');
	const add_more_btn = document.getElementById('add-more-btn');
	currentPrefix = nextFileFormID.toString();
	nextFileFormID += 1

	for (const elem of template.children) {
		clone = elem.cloneNode(true)
		updateFormsetIDs(clone, currentPrefix)
		form.insertBefore(clone, add_more_btn);
	}

	const formset_handler = document.getElementById('id_submit-TOTAL_FORMS');
	formset_handler.value = parseInt(formset_handler.value) + 1;
}

function deleteThisFileForm() {
	event.target.closest('.entry').remove();

	// contains buttons as well!!
	const form = document.getElementById('input-form')
	console.log(form)
	let allFileForms = Array.from(form.children).filter(child =>
		child.classList.contains('entry')
	);
	console.log(allFileForms);
	let i = 0;
	for (const fileForm of allFileForms) {
		updateFormsetIDs(fileForm, i);
		i += 1
	}
	nextFileFormID -= 1;

	const formset_handler = document.getElementById('id_submit-TOTAL_FORMS');
	formset_handler.value = parseInt(formset_handler.value) - 1;
}

function handleChangedFileType() {
	fileLabel = event.target.closest('.entry').querySelector('.file-label');
	currentOption = event.target.value;
	fileInput = fileLabel.querySelector('.file-input')

	let newLabelText = undefined;
	// changing html attributes to match input type,
	// (maestro -> webkitdir), (toptrj -> multiple files)
	//
	// changing label text as well
	if (currentOption === "MaestroDir") {
		newLabelText = "Upload directory...";
		fileInput.removeAttribute("multiple");
		fileInput.setAttribute("webkitdirectory", "")
	} else if (currentOption === "TopTrjPair") {
		newLabelText = "Upload files..."
		fileInput.setAttribute("multiple", "");
		fileInput.removeAttribute("webkitdirectory");
	}

	// changing the text to match selected input type
	for (let i = 0; i < fileLabel.childNodes.length; i++) {
		if (fileLabel.childNodes[i].nodeType === Node.TEXT_NODE) {
			fileLabel.childNodes[i].nodeValue = newLabelText;
			break;
		}
	}

	// removing any currently chosen files
	fileInput.value = "";
}

function handleNewFiles() {
	fileInput = event.target;
	filePathsInput = event.target.closest('.entry').querySelector('.file-paths');
	fileLabel = event.target.closest('.entry').querySelector('.file-label');

	let chosenFiles = "";
	if (fileInput.hasAttribute("multiple")) {
		chosenFiles = 'Chosen files: ' + Array.from(fileInput.files, (x) => x.name).join(', ');
	} else if (fileInput.hasAttribute("webkitdirectory")) {
		const paths = {};
		const dt = new DataTransfer();
		// we need to replace FileList object to remove
		// deduplicate file names...
		let i = 0
		for (const file of fileInput.files) {
			const filePath = file.webkitRelativePath;
			const prefixedFileName = `BROWSER_PREFIX${i}_${file.name}`;
			paths[prefixedFileName] = filePath;
			const prefixedFile = new File([file], prefixedFileName);
			dt.items.add(prefixedFile);
			i += 1;

			if (chosenFiles === "") {
				chosenFiles = 'Chosen directory: '.concat(file.webkitRelativePath.split("/")[0]);
			}
		}
		filePathsInput.value = JSON.stringify(paths);
		fileInput.files = dt.files;
	}

	// setting new name for the label to show loaded files
	for (let i = 0; i < fileLabel.childNodes.length; i++) {
		if (fileLabel.childNodes[i].nodeType === Node.TEXT_NODE) {
			fileLabel.childNodes[i].nodeValue = chosenFiles;
			break;
		}
	}
}

function toggleExperimentalValues() {
	const array = document.querySelectorAll('input.val');
	add_VOI_button = document.getElementById("id_add_VOI");
	array.forEach((element) => add_VOI_button.checked ? element.classList.remove("hidden") : element.classList.add("hidden"));
}
