(function () {
    function toggleSidebar(show) {
        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('mobile-overlay');
        if (!sidebar || !overlay) {
            return;
        }

        if (show) {
            sidebar.classList.remove('-translate-x-full');
            overlay.classList.remove('hidden');
        } else {
            sidebar.classList.add('-translate-x-full');
            overlay.classList.add('hidden');
        }
    }

    function bindConfirmModals() {
        document.querySelectorAll('[data-confirm-open]').forEach((button) => {
            button.addEventListener('click', () => {
                const id = button.getAttribute('data-confirm-open');
                const modal = document.getElementById(id);
                if (modal) {
                    modal.classList.remove('hidden');
                }
            });
        });

        document.querySelectorAll('[data-confirm-close]').forEach((button) => {
            button.addEventListener('click', () => {
                const id = button.getAttribute('data-confirm-close');
                const modal = document.getElementById(id);
                if (modal) {
                    modal.classList.add('hidden');
                }
            });
        });
    }

    function bindFlashMessages() {
        const flashMessages = document.querySelectorAll('.flash-message');
        if (!flashMessages.length) {
            return;
        }

        setTimeout(() => {
            flashMessages.forEach((el) => {
                el.classList.add('flash-hide');
                setTimeout(() => el.remove(), 400);
            });
        }, 3500);
    }

    function bindSortableTables() {
        document.querySelectorAll('[data-sortable-table]').forEach((table) => {
            const tbody = table.querySelector('tbody');
            if (!tbody) {
                return;
            }

            table.querySelectorAll('[data-sort-col]').forEach((button) => {
                let asc = true;
                button.addEventListener('click', () => {
                    const col = Number(button.getAttribute('data-sort-col'));
                    const rows = Array.from(tbody.querySelectorAll('tr')).filter((row) => row.querySelectorAll('td').length > 0);
                    rows.sort((a, b) => {
                        const aText = (a.children[col]?.innerText || '').trim().toLowerCase();
                        const bText = (b.children[col]?.innerText || '').trim().toLowerCase();
                        return asc
                            ? aText.localeCompare(bText, undefined, { numeric: true })
                            : bText.localeCompare(aText, undefined, { numeric: true });
                    });
                    rows.forEach((row) => tbody.appendChild(row));
                    asc = !asc;
                });
            });
        });
    }

    window.toggleSidebar = toggleSidebar;

    document.addEventListener('DOMContentLoaded', () => {
        bindConfirmModals();
        bindFlashMessages();
        bindSortableTables();
    });
})();
