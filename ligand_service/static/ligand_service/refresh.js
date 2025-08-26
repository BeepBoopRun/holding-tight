document.addEventListener("DOMContentLoaded", (event) => {
    const statusInfo = document.getElementById('status-info'); 

    let remainingTime = 30;

    function refreshSite() {
	remainingTime -= 1;
	if(remainingTime <= 0) {
	    location.reload()
	}
	statusInfo.textContent = statusInfo.textContent.slice(0, -2) + remainingTime
    }

    setInterval(refreshSite, 1000)
});
