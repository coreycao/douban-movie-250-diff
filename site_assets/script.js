/* Douban Movie 250 Diff — minimal JS */

(function () {
    'use strict';

    // Mobile hamburger menu toggle
    var hamburger = document.querySelector('.hamburger');
    var nav = document.querySelector('.site-nav');

    if (hamburger && nav) {
        hamburger.addEventListener('click', function () {
            nav.classList.toggle('open');
            var expanded = nav.classList.contains('open');
            hamburger.setAttribute('aria-expanded', expanded);
        });

        // Close nav when clicking outside
        document.addEventListener('click', function (e) {
            if (!nav.contains(e.target) && !hamburger.contains(e.target)) {
                nav.classList.remove('open');
                hamburger.setAttribute('aria-expanded', 'false');
            }
        });
    }

    // Expand/collapse all day records (month pages)
    var toggleAll = document.getElementById('toggleAll');
    if (toggleAll) {
        var details = Array.prototype.slice.call(
            document.querySelectorAll('details.diff-detail'));

        toggleAll.addEventListener('click', function () {
            var anyClosed = details.some(function (d) { return !d.open; });
            details.forEach(function (d) { d.open = anyClosed; });
            toggleAll.textContent = anyClosed ? '全部收起' : '全部展开';
            toggleAll.setAttribute('aria-pressed', String(anyClosed));
        });
    }

    // On month pages, open the newest day record so the page isn't a bare list
    var firstDetail = document.querySelector('details.diff-detail');
    if (firstDetail && document.getElementById('toggleAll')) {
        firstDetail.open = true;
    }
})();
