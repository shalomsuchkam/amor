// Общий помощник: CSRF-токен для fetch-запросов.
window.csrf = () => document.querySelector('meta[name=csrf]').content;
