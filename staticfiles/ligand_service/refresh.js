document.addEventListener("DOMContentLoaded", (event) => {
    const statusInfo = document.getElementById('refresh-status'); 

    let remainingTime = 30;

    function refreshSite() {
	remainingTime -= 1;
	if(remainingTime <= 0) {
	    location.reload();
	    clearInterval(refreshIntervalId);
	}
	statusInfo.textContent = "Page will refresh in " + remainingTime + "s";
	statusInfo.classList.remove("invisible")
    }

    var refreshIntervalId = setInterval(refreshSite, 1000);
});


