(function(){
'use strict';
var sidebar=document.getElementById('navigation'),shade=document.getElementById('screen-shade'),open=document.getElementById('sidebar-open'),close=document.getElementById('sidebar-close');
function setNav(show){if(!sidebar)return;sidebar.classList.toggle('is-open',show);shade.classList.toggle('is-open',show);if(open)open.setAttribute('aria-expanded',String(show));}
if(open)open.addEventListener('click',function(){setNav(true);});
if(close)close.addEventListener('click',function(){setNav(false);});
if(shade)shade.addEventListener('click',function(){setNav(false);});
document.addEventListener('keydown',function(event){if(event.key==='Escape')setNav(false);});
document.querySelectorAll('form[data-confirm]').forEach(function(form){form.addEventListener('submit',function(event){if(!window.confirm(form.dataset.confirm||'Confirm this action?'))event.preventDefault();});});
})();
