import React from 'react';
import ReactDOM from 'react-dom/client';
import './styles/global.css';

function Bootstrap() {
  return <main className="boot">Tienda Digital Scrum</main>;
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <Bootstrap />
  </React.StrictMode>
);

