document.addEventListener('DOMContentLoaded', function() {
    function loadPage(url, pushState=true) {
        fetch(url, {headers: {'X-Requested-With': 'XMLHttpRequest'}})
            .then(response => response.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newContent = doc.querySelector('.spa-content');
                if (newContent) {
                    document.querySelector('.spa-content').innerHTML = newContent.innerHTML;
                    if (pushState) history.pushState({url: url}, '', url);
                }
            });
    }
    document.body.addEventListener('click', function(e) {
        const link = e.target.closest('a[data-spa]');
        if (link) {
            e.preventDefault();
            loadPage(link.getAttribute('href'));
        }
    });
    window.addEventListener('popstate', function(e) {
        if (e.state && e.state.url) {
            loadPage(e.state.url, false);
        }
    });
});
