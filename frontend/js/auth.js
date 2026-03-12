// auth.js — Session management & guards

const API = 'http://localhost:8000';

function requireAuth() {
    if (!sessionStorage.getItem('hr_token')) {
        window.location.href = 'index.html';
        return false;
    }
    return true;
}

function logout() {
    sessionStorage.removeItem('hr_token');
    sessionStorage.removeItem('hr_user');
    window.location.href = 'index.html';
}

function getUser() {
    return sessionStorage.getItem('hr_user') || 'Admin';
}

// Global toast notification
function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span class="toast-icon">${icons[type] || 'ℹ️'}</span>
                     <span class="toast-msg">${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'fadeIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}
