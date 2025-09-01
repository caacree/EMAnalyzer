import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './index.css'
import '@annotorious/react/annotorious-react.css';
import OpenSeadragon from 'openseadragon';
import 'openseadragon-filtering';


ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
