// Shared API helpers for writer templates
(function(window){
  // CSRF helper (reads cookie)
  function getCookie(name){
    const v = `; ${document.cookie}`.split(`; ${name}=`);
    if (v.length === 2) return v.pop().split(';').shift();
    return null;
  }

  const CSRF_TOKEN = getCookie('csrftoken');

  // API base paths
  const API = {
    POSTS: '/api/blog/posts/',
    SITES: '/api/sites/',
    AUTHORS: '/api/blog/authors/',
    CATEGORIES: '/api/blog/categories/',
    POSTIMAGES: '/api/blog/postimages/',
  };

  // Fetch wrapper that includes credentials and CSRF when needed
  async function apiFetch(path, opts = {}){
    const init = Object.assign({ credentials: 'same-origin' }, opts);
    init.headers = init.headers || {};
    if (!init.headers['Content-Type'] && !(init.body instanceof FormData)){
      init.headers['Content-Type'] = 'application/json';
    }
    // Add CSRF for unsafe methods
    const method = (init.method || 'GET').toUpperCase();
    if (['POST','PUT','PATCH','DELETE'].includes(method)){
      init.headers['X-CSRFToken'] = CSRF_TOKEN;
    }
    return fetch(path, init);
  }

  window.WriterAPI = {
    apiFetch,
    API,
    CSRF_TOKEN,
    getCookie
  };
})(window);
