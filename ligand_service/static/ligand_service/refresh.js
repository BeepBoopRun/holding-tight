document.addEventListener("DOMContentLoaded", (event) => {
    const statusInfo = document.getElementById('status-info'); 

    let remainingTime = 30;

    function refreshSite() {
	remainingTime -= 1;
	if(remainingTime <= 0) {
	    location.reload();
	    clearInterval(refreshIntervalId);
	}
	statusInfo.textContent = statusInfo.textContent.slice(0, -2) + remainingTime;
    }

    var refreshIntervalId = setInterval(refreshSite, 1000);
});


