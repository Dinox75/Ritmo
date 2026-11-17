document.getElementById('authorize').onsubmit = async event => {
  event.preventDefault();
  const input = document.getElementById('code');
  const code = input.value; input.value = '';
  try {
    const response = await fetch('/api/session', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})});
    const result = await response.json();
    if (!response.ok) throw Error(result.error);
    location.replace('/');
  } catch(error) { document.getElementById('error').textContent = error.message; }
};
