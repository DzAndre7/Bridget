(function(){
  var canvas = document.getElementById('bcanvas');
  var ctx = canvas.getContext('2d');
  var W, H, cx, cy;

  function resize(){
    var rect = canvas.getBoundingClientRect();
    W = canvas.width = rect.width;
    H = canvas.height = rect.height;
    cx = W/2; cy = H/2;
  }
  window.addEventListener('resize', resize);

  var t = 0, modo = 'reposo';
  var sacudida = 0; // se dispara al empujar, y decae: hace "reaccionar" a la presencia

  var cfg = {
    col: '40,140,150',
    cant: 140, disp: 100, vel: 100, sz: 100,
    react: 100, core: 100, flat: 78, opac: 65
  };

  // --- Cargar configuración guardada (si existe) ---
  function aplicarConfigGuardada(){
    if(window.pywebview && window.pywebview.api){
      window.pywebview.api.cargar_config().then(function(txt){
        if(txt){
          try {
            var guardada = JSON.parse(txt);
            for(var k in guardada){ if(k in cfg) cfg[k] = guardada[k]; }
            sincronizarControles();
          } catch(e){}
        }
      });
    }
  }

  // --- Guardar configuración en disco ---
  var guardarTimer = null;
  function guardarConfig(){
    if(!(window.pywebview && window.pywebview.api)) return;
    // esperamos un poquito para no guardar en cada micro-movimiento del slider
    clearTimeout(guardarTimer);
    guardarTimer = setTimeout(function(){
      window.pywebview.api.guardar_config(JSON.stringify(cfg));
    }, 400);
  }

  var P = [];
  function rebuild(n){
    P = [];
    for(var i=0;i<n;i++){
      P.push({
        a: Math.random()*Math.PI*2,
        r: 30 + Math.random()*95,
        s: 0.25 + Math.random()*0.9,
        sz: 0.6 + Math.random()*1.8,
        tw: Math.random()*Math.PI*2
      });
    }
  }
  rebuild(cfg.cant);

  function voz(){
    var base = (modo==='reposo')
      ? (0.12 + 0.06*Math.sin(t*0.04))
      : (0.45 + 0.55*Math.abs(Math.sin(t*0.07))*(0.55+0.45*Math.sin(t*0.21)));
    return base * (cfg.react/100) + sacudida;
  }

  function loop(){
    t += cfg.vel/100;
    if(sacudida > 0) sacudida *= 0.92; // la reacción al empujón se calma de a poco
    ctx.clearRect(0,0,W,H);
    var v = voz();
    var col = cfg.col;
    var flat = cfg.flat/100;

    if(cfg.core > 0){
      var coreR = (5 + v*5) * (cfg.core/100);
      var g = ctx.createRadialGradient(cx,cy,0,cx,cy,Math.max(1,coreR*4));
      g.addColorStop(0,'rgba('+col+','+(0.5+v*0.4)+')');
      g.addColorStop(1,'rgba('+col+',0)');
      ctx.fillStyle = g;
      ctx.beginPath(); ctx.arc(cx,cy,Math.max(1,coreR*4),0,Math.PI*2); ctx.fill();
      ctx.beginPath(); ctx.arc(cx,cy,coreR,0,Math.PI*2);
      ctx.fillStyle = 'rgba(235,250,252,'+(0.7+v*0.3)+')'; ctx.fill();
    }

    for(var i=0;i<P.length;i++){
      var p = P[i];
      p.a += 0.0016*p.s*(0.5+v);
      p.tw += 0.05;
      var rr = (p.r*(cfg.disp/100)) + v*55*p.s*(cfg.disp/100);
      var x = cx + Math.cos(p.a)*rr;
      var y = cy + Math.sin(p.a)*rr*flat;
      var alpha = (0.15 + v*0.55)*(0.6+0.4*Math.sin(p.tw));
      var size = p.sz*(0.5+v*0.9)*(cfg.sz/100);
      ctx.beginPath();
      ctx.arc(x,y,Math.max(0.2,size),0,Math.PI*2);
      ctx.fillStyle = 'rgba('+col+','+alpha+')';
      ctx.fill();
    }
    requestAnimationFrame(loop);
  }
  resize();
  loop();

  // --- Panel: abrir / cerrar con empujón ---
  var btn = document.getElementById('btn-panel');
  var panel = document.getElementById('panel');
  var escenario = document.getElementById('escenario');

  btn.addEventListener('click', function(){
    var abierto = panel.classList.toggle('abierto');
    escenario.classList.toggle('empujado', abierto);
    sacudida = 0.35; // la presencia "siente" el empujón
    // recalculamos el centro después de que termine la transición
    setTimeout(resize, 360);
  });

  // --- Controles del editor ---
  function bind(id, key, out){
    var el = document.getElementById(id);
    el.addEventListener('input', function(){
      cfg[key] = +el.value;
      document.getElementById(out).textContent = el.value;
      if(key === 'cant') rebuild(cfg.cant);
      guardarConfig();
    });
  }
  bind('s-cant','cant','v-cant');
  bind('s-disp','disp','v-disp');
  bind('s-vel','vel','v-vel');
  bind('s-sz','sz','v-sz');
  bind('s-react','react','v-react');
  bind('s-core','core','v-core');
  bind('s-flat','flat','v-flat');

  // Control de opacidad del fondo
  var escenarioEl = document.getElementById('escenario');
  function aplicarFondo(){
    escenarioEl.style.background = 'rgba(10, 14, 20, ' + (cfg.opac/100) + ')';
  }

  aplicarFondo(); // aplica el valor inicial

  document.getElementById('s-opac').addEventListener('input', function(){
    cfg.opac = +this.value;
    document.getElementById('v-opac').textContent = this.value;
    aplicarFondo();
    guardarConfig();
  });

  // Selector RGB
  var sR = document.getElementById('s-r');
  var sG = document.getElementById('s-g');
  var sB = document.getElementById('s-b');
  var preview = document.getElementById('preview-color');
  var vColor = document.getElementById('v-color');

  function actualizarColor(){
    var r = +sR.value, g = +sG.value, b = +sB.value;
    cfg.col = r + ',' + g + ',' + b;
    preview.style.background = 'rgb(' + cfg.col + ')';
    vColor.textContent = r + ', ' + g + ', ' + b;
    document.getElementById('blabel').style.color = 'rgb(' + cfg.col + ')';
  }

  sR.addEventListener('input', function(){ actualizarColor(); guardarConfig(); });
  sG.addEventListener('input', function(){ actualizarColor(); guardarConfig(); });
  sB.addEventListener('input', function(){ actualizarColor(); guardarConfig(); });
  actualizarColor(); // aplica el valor inicial

  // Pone todos los controles en sus valores actuales de cfg
  function sincronizarControles(){
    document.getElementById('s-cant').value = cfg.cant;  document.getElementById('v-cant').textContent = cfg.cant;
    document.getElementById('s-disp').value = cfg.disp;  document.getElementById('v-disp').textContent = cfg.disp;
    document.getElementById('s-vel').value  = cfg.vel;   document.getElementById('v-vel').textContent  = cfg.vel;
    document.getElementById('s-sz').value   = cfg.sz;    document.getElementById('v-sz').textContent   = cfg.sz;
    document.getElementById('s-react').value= cfg.react; document.getElementById('v-react').textContent= cfg.react;
    document.getElementById('s-core').value = cfg.core;  document.getElementById('v-core').textContent = cfg.core;
    document.getElementById('s-flat').value = cfg.flat;  document.getElementById('v-flat').textContent = cfg.flat;
    document.getElementById('s-opac').value = cfg.opac;  document.getElementById('v-opac').textContent = cfg.opac;
    var rgb = cfg.col.split(',');
    document.getElementById('s-r').value = rgb[0];
    document.getElementById('s-g').value = rgb[1];
    document.getElementById('s-b').value = rgb[2];
    rebuild(cfg.cant);
    actualizarColor();
    aplicarFondo();
  }

  window.setEstado = function(m){ modo = m; };
  window.addEventListener('pywebviewready', aplicarConfigGuardada);
})();