// ======================================================
// HU7 · Carga académica de los docentes
// HU8 · Validación de disponibilidad al asignar clases
// ======================================================

document.addEventListener("DOMContentLoaded", () => {

    const tablaCarga = document.getElementById("tabla-carga");
    const buscar = document.getElementById("buscar-carga");
    const filtroPeriodo = document.getElementById("filtro-periodo");

    const detalle = document.getElementById("detalle-carga");
    const detalleTitulo = document.getElementById("detalle-titulo");
    const detalleSubtitulo = document.getElementById("detalle-subtitulo");
    const tablaDetalle = document.getElementById("tabla-detalle");
    const tablaGrupos = document.getElementById("tabla-grupos");

    const modalGrupo = document.getElementById("modal-grupo");
    const formGrupo = document.getElementById("form-grupo");
    const modalClase = document.getElementById("modal-clase");
    const formClase = document.getElementById("form-clase");

    const claseDocente = document.getElementById("clase-docente");
    const claseGrupo = document.getElementById("clase-grupo");
    const claseDia = document.getElementById("clase-dia");
    const claseSede = document.getElementById("clase-sede");
    const claseFranja = document.getElementById("clase-franja");
    const resultado = document.getElementById("resultado-validacion");
    const guardarClase = document.getElementById("guardar-clase");

    const NOMBRE_DIA = { Miercoles: "Miércoles", Sabado: "Sábado" };
    const nombreDia = (d) => NOMBRE_DIA[d] || d;

    let saliendo = false;
    window.addEventListener("pagehide", () => { saliendo = true; });

    let docenteAbierto = null;
    let gruposCargados = [];
    let temporizador = null;
    let validacionActual = 0;

    // ---------- utilidades ----------

    function notificar(mensaje, tipo = "informacion") {
        if (window.AulaSynModal && typeof window.AulaSynModal.notificar === "function") {
            window.AulaSynModal.notificar(mensaje, tipo);
        } else {
            console.log(mensaje);
        }
    }

    async function api(ruta, opciones = {}) {
        const config = { credentials: "same-origin", ...opciones };
        if (opciones.body !== undefined) {
            config.headers = { "Content-Type": "application/json" };
            config.body = JSON.stringify(opciones.body);
        }
        let respuesta;
        try {
            respuesta = await fetch(ruta, config);
        } catch (error) {
            // Al cambiar de página el navegador cancela las peticiones en curso: no es un error real.
            if (saliendo) return new Promise(() => {});
            return {
                ok: false,
                estado: 0,
                datos: { mensaje: "No se pudo conectar con el servidor. Inténtalo nuevamente." }
            };
        }
        const datos = await respuesta.json().catch(() => ({}));
        return { ok: respuesta.ok, estado: respuesta.status, datos };
    }

    function celda(fila, contenido, clase) {
        const td = document.createElement("td");
        if (contenido instanceof Node) {
            td.appendChild(contenido);
        } else {
            td.textContent = contenido;
        }
        if (clase) td.className = clase;
        fila.appendChild(td);
        return td;
    }

    function filaMensaje(cuerpo, columnas, texto) {
        cuerpo.replaceChildren();
        const tr = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = columnas;
        td.className = "mensaje-tabla";
        td.textContent = texto;
        tr.appendChild(td);
        cuerpo.appendChild(tr);
    }

    function mostrarModal(m) {
        m.classList.add("visible");
        m.setAttribute("aria-hidden", "false");
        document.body.style.overflow = "hidden";
    }

    function ocultarModal(m) {
        m.classList.remove("visible");
        m.setAttribute("aria-hidden", "true");
        document.body.style.overflow = "";
    }

    function opcion(select, valor, texto) {
        const o = document.createElement("option");
        o.value = valor;
        o.textContent = texto;
        select.appendChild(o);
    }

    function reiniciarSelect(select, textoInicial) {
        select.replaceChildren();
        opcion(select, "", textoInicial);
    }

    // ---------- datos para los formularios ----------

    async function cargarDatos() {
        const r = await api("/api/carga-academica/datos");
        if (!r.ok) {
            notificar(r.datos.mensaje || "No fue posible cargar los datos.", "error");
            return;
        }
        const d = r.datos;

        reiniciarSelect(filtroPeriodo, "Todos los periodos");
        d.periodos.forEach((p) => opcion(filtroPeriodo, p, p));

        reiniciarSelect(claseDocente, "Selecciona un docente");
        d.docentes.forEach((x) => opcion(claseDocente, x.id_usuario, x.nombre));

        reiniciarSelect(claseDia, "Selecciona un día");
        d.dias.forEach((x) => opcion(claseDia, x, nombreDia(x)));

        reiniciarSelect(claseSede, "Selecciona una sede");
        d.sedes.forEach((x) => opcion(claseSede, x.id_sede, x.nombre));

        reiniciarSelect(claseFranja, "Selecciona una franja");
        d.franjas.forEach((x) =>
            opcion(claseFranja, x.id_franja, `${x.nombre} (${x.hora_inicio}–${x.hora_fin})`));

        const selAsignatura = document.getElementById("grupo-asignatura");
        reiniciarSelect(selAsignatura, "Selecciona una asignatura");
        d.asignaturas.forEach((x) =>
            opcion(selAsignatura, x.id_asignatura, `${x.semestre ? "Sem. " + x.semestre + " · " : ""}${x.nombre}`));

        await cargarGrupos();
    }

    async function cargarGrupos() {
        const r = await api("/api/grupos");
        reiniciarSelect(claseGrupo, "Selecciona un grupo");
        if (r.ok) {
            gruposCargados = r.datos.grupos;
            gruposCargados.forEach((g) =>
                opcion(claseGrupo, g.id_grupo, `${g.periodo} · ${g.codigo} · ${g.asignatura}`));
            pintarGrupos();
        } else {
            filaMensaje(tablaGrupos, 5, r.datos.mensaje || "No fue posible cargar los grupos.");
        }
    }

    function pintarGrupos() {
        const lista = gruposCargados.filter((g) => !filtroPeriodo.value || g.periodo === filtroPeriodo.value);
        if (!lista.length) {
            filaMensaje(tablaGrupos, 5, "No hay grupos creados. Usa \"Crear grupo\" para agregar uno.");
            return;
        }
        tablaGrupos.replaceChildren();
        lista.forEach((g) => {
            const tr = document.createElement("tr");
            celda(tr, g.periodo);
            celda(tr, g.codigo);

            const bloque = document.createElement("div");
            const nombre = document.createElement("span");
            nombre.className = "docente-nombre";
            nombre.textContent = g.asignatura;
            bloque.appendChild(nombre);
            if (g.codigo_asignatura) {
                const cod = document.createElement("span");
                cod.className = "detalle-horario";
                cod.textContent = g.codigo_asignatura;
                bloque.appendChild(cod);
            }
            celda(tr, bloque);
            celda(tr, g.semestre ? String(g.semestre) : "—");
            celda(tr, String(g.clases), "cifra-carga");
            tablaGrupos.appendChild(tr);
        });
    }

    // ---------- HU7: resumen por docente ----------

    async function cargarResumen() {
        const params = new URLSearchParams();
        if (buscar.value.trim()) params.set("docente", buscar.value.trim());
        if (filtroPeriodo.value) params.set("periodo", filtroPeriodo.value);

        const r = await api("/api/carga-academica?" + params.toString());
        if (!r.ok) {
            filaMensaje(tablaCarga, 6, r.datos.mensaje || "No fue posible cargar la carga académica.");
            return;
        }
        const docentes = r.datos.docentes;
        if (!docentes.length) {
            filaMensaje(tablaCarga, 6, "No se encontraron docentes.");
            return;
        }

        tablaCarga.replaceChildren();
        docentes.forEach((d) => {
            const tr = document.createElement("tr");

            const bloque = document.createElement("div");
            const nombre = document.createElement("span");
            nombre.className = "docente-nombre";
            nombre.textContent = d.docente;
            const correo = document.createElement("span");
            correo.className = "docente-correo";
            correo.textContent = d.correo;
            bloque.append(nombre, correo);

            celda(tr, bloque);
            celda(tr, String(d.asignaturas), "cifra-carga");
            celda(tr, String(d.grupos), "cifra-carga");
            celda(tr, String(d.clases), "cifra-carga");
            celda(tr, d.horas_semana + " h", "cifra-carga");

            const boton = document.createElement("button");
            boton.type = "button";
            boton.className = "boton-estado";
            boton.textContent = "Ver detalle";
            boton.addEventListener("click", () => abrirDetalle(d.id_usuario));
            celda(tr, boton);

            tablaCarga.appendChild(tr);
        });
    }

    // ---------- HU7: materias y grupos de un docente ----------

    async function abrirDetalle(idDocente) {
        docenteAbierto = idDocente;
        const params = filtroPeriodo.value ? "?periodo=" + encodeURIComponent(filtroPeriodo.value) : "";
        const r = await api(`/api/carga-academica/${idDocente}${params}`);
        if (!r.ok) {
            notificar(r.datos.mensaje || "No fue posible cargar el detalle.", "error");
            return;
        }

        const { docente, clases } = r.datos;
        detalleTitulo.textContent = "Carga de " + docente.docente;
        detalleSubtitulo.textContent = filtroPeriodo.value
            ? "Periodo " + filtroPeriodo.value
            : "Todos los periodos";

        if (!clases.length) {
            filaMensaje(tablaDetalle, 7, "Este docente no tiene clases asignadas.");
        } else {
            tablaDetalle.replaceChildren();
            clases.forEach((c) => {
                const tr = document.createElement("tr");

                const bloque = document.createElement("div");
                const nombre = document.createElement("span");
                nombre.className = "docente-nombre";
                nombre.textContent = c.asignatura;
                const info = document.createElement("span");
                info.className = "detalle-horario";
                info.textContent = [c.semestre ? "Semestre " + c.semestre : "", c.codigo_asignatura || ""]
                    .filter(Boolean).join(" · ");
                bloque.append(nombre, info);

                celda(tr, bloque);
                celda(tr, c.grupo);
                celda(tr, c.periodo);
                celda(tr, nombreDia(c.dia_semana));
                celda(tr, `${c.hora_inicio}–${c.hora_fin}`);
                celda(tr, c.sede);

                const quitar = document.createElement("button");
                quitar.type = "button";
                quitar.className = "boton-estado";
                quitar.textContent = "Quitar";
                quitar.addEventListener("click", () => quitarClase(c, quitar));
                celda(tr, quitar);

                tablaDetalle.appendChild(tr);
            });
        }

        detalle.hidden = false;
        detalle.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    async function quitarClase(clase, boton) {
        let aceptado = true;
        if (window.AulaSynModal && typeof window.AulaSynModal.confirmar === "function") {
            aceptado = await window.AulaSynModal.confirmar({
                titulo: "Quitar clase",
                mensaje: `¿Quitar ${clase.asignatura} (grupo ${clase.grupo}) del ${nombreDia(clase.dia_semana)} ${clase.hora_inicio}–${clase.hora_fin}?`,
                textoConfirmar: "Quitar",
                botonPeligro: true
            });
        }
        if (!aceptado) return;

        boton.disabled = true;
        const r = await api(`/api/asignaciones/${clase.id_asignacion}`, { method: "DELETE" });
        notificar(r.datos.mensaje || "No fue posible quitar la clase.", r.ok ? "exito" : "error");
        boton.disabled = false;
        if (r.ok) {
            cargarGrupos();
            await Promise.all([cargarResumen(), abrirDetalle(docenteAbierto)]);
        }
    }

    // ---------- HU8: asignar clase con validación ----------

    function mostrarResultado(tipo, mensaje, avisos = []) {
        resultado.replaceChildren();
        resultado.className = "resultado-validacion " + tipo;
        resultado.append(document.createTextNode(mensaje));
        avisos.forEach((a) => {
            const l = document.createElement("span");
            l.className = "linea-aviso";
            l.textContent = "⚠ " + a;
            resultado.appendChild(l);
        });
        resultado.hidden = false;
    }

    function ocultarResultado() {
        resultado.hidden = true;
        resultado.replaceChildren();
    }

    function datosClase() {
        return {
            id_grupo: Number(claseGrupo.value),
            id_usuario: Number(claseDocente.value),
            id_sede: Number(claseSede.value),
            id_franja: Number(claseFranja.value),
            dia_semana: claseDia.value
        };
    }

    function formularioCompleto() {
        return [claseDocente, claseGrupo, claseDia, claseSede, claseFranja].every((c) => c.value);
    }

    function programarValidacion() {
        clearTimeout(temporizador);
        ocultarResultado();
        if (!formularioCompleto()) return;
        temporizador = setTimeout(validarEnVivo, 300);
    }

    async function validarEnVivo() {
        const turno = ++validacionActual;
        const r = await api("/api/asignaciones/validar", { method: "POST", body: datosClase() });
        if (turno !== validacionActual) return;  // llegó una respuesta más nueva
        if (!r.ok) {
            mostrarResultado("invalido", r.datos.mensaje || "No fue posible validar la asignación.");
        } else if (!r.datos.valido) {
            mostrarResultado("invalido", r.datos.mensaje);
        } else if (r.datos.advertencias && r.datos.advertencias.length) {
            mostrarResultado("aviso", "El horario es válido.", r.datos.advertencias);
        } else {
            mostrarResultado("valido", "El docente está disponible en este horario.");
        }
    }

    [claseDocente, claseGrupo, claseDia, claseSede, claseFranja].forEach((c) =>
        c.addEventListener("change", programarValidacion));

    formClase.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        if (!formularioCompleto()) {
            notificar("Selecciona el docente, el grupo, el día, la sede y la franja horaria.", "advertencia");
            return;
        }
        guardarClase.disabled = true;
        const r = await api("/api/asignaciones", { method: "POST", body: datosClase() });
        guardarClase.disabled = false;

        if (!r.ok) {
            mostrarResultado("invalido", r.datos.mensaje || "No fue posible asignar la clase.");
            return;
        }
        notificar(r.datos.mensaje, "exito");
        (r.datos.advertencias || []).forEach((a) => notificar(a, "advertencia"));
        const idDocente = Number(claseDocente.value);
        formClase.reset();
        ocultarResultado();
        ocultarModal(modalClase);
        await cargarResumen();
        cargarGrupos();
        if (detalle.hidden === false && docenteAbierto === idDocente) await abrirDetalle(idDocente);
    });

    // ---------- crear grupo ----------

    formGrupo.addEventListener("submit", async (evento) => {
        evento.preventDefault();
        const boton = document.getElementById("guardar-grupo");
        boton.disabled = true;
        const r = await api("/api/grupos", {
            method: "POST",
            body: {
                periodo: document.getElementById("grupo-periodo").value.trim(),
                codigo: document.getElementById("grupo-codigo").value.trim(),
                id_asignatura: Number(document.getElementById("grupo-asignatura").value) || null,
                codigo_asignatura: document.getElementById("grupo-codigo-asignatura").value.trim()
            }
        });
        boton.disabled = false;
        notificar(r.datos.mensaje || "No fue posible crear el grupo.", r.ok ? "exito" : "error");
        if (!r.ok) return;
        formGrupo.reset();
        ocultarModal(modalGrupo);
        await cargarDatos();
    });

    // ---------- eventos de la página ----------

    document.getElementById("abrir-modal-clase").addEventListener("click", () => {
        formClase.reset();
        ocultarResultado();
        mostrarModal(modalClase);
    });
    document.getElementById("abrir-modal-grupo").addEventListener("click", () => {
        formGrupo.reset();
        mostrarModal(modalGrupo);
    });
    ["cerrar-modal-clase", "cancelar-clase"].forEach((id) =>
        document.getElementById(id).addEventListener("click", () => ocultarModal(modalClase)));
    ["cerrar-modal-grupo", "cancelar-grupo"].forEach((id) =>
        document.getElementById(id).addEventListener("click", () => ocultarModal(modalGrupo)));
    document.getElementById("cerrar-detalle").addEventListener("click", () => {
        detalle.hidden = true;
        docenteAbierto = null;
    });

    let esperaBusqueda = null;
    buscar.addEventListener("input", () => {
        clearTimeout(esperaBusqueda);
        esperaBusqueda = setTimeout(cargarResumen, 300);
    });
    filtroPeriodo.addEventListener("change", async () => {
        pintarGrupos();
        await cargarResumen();
        if (!detalle.hidden && docenteAbierto) await abrirDetalle(docenteAbierto);
    });

    cargarDatos().then(cargarResumen);
});
