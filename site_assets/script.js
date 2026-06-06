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

    // Open the first <details> on the home page's latest diff if present
    var firstDetail = document.querySelector('.latest-section details.diff-detail');
    if (firstDetail) {
        firstDetail.open = true;
    }
})();
