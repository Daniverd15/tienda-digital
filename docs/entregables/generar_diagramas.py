"""Generador de diagramas UML para la documentación de Tienda Digital.

Produce imágenes PNG en docs/entregables/imagenes/ que luego se embeben en los
documentos .docx. Los diagramas se dibujan con matplotlib para tener control
total del estilo y que se vean limpios y entendibles.
"""
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Rectangle, Ellipse, Polygon
from matplotlib.lines import Line2D

OUT = Path(__file__).parent / "imagenes"
OUT.mkdir(parents=True, exist_ok=True)

# Colores corporativos Distrito Urbano
BRAND      = "#1f7a5c"
BRAND_LITE = "#d4f0e1"
ACCENT     = "#f59e0b"
ACCENT_LITE= "#fed7aa"
GRAY       = "#4c5960"
GRAY_LITE  = "#e6e9e3"
TEXT       = "#172026"
WARN_BG    = "#fef3c7"
INFO_BG    = "#dbeafe"
ROSE_BG    = "#fce7f3"


def save(fig, name):
    path = OUT / f"{name}.png"
    fig.savefig(path, dpi=140, bbox_inches="tight", facecolor="white", pad_inches=0.3)
    plt.close(fig)
    print(f"  OK  {path.relative_to(OUT.parent.parent.parent)}")


# =============================================================================
# 1. DIAGRAMA DE CASOS DE USO
# =============================================================================

def diagrama_casos_uso():
    fig, ax = plt.subplots(figsize=(16, 11))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 11)
    ax.axis("off")

    # Título
    ax.text(8, 10.5, "Diagrama de Casos de Uso — Distrito Urbano", fontsize=16,
            fontweight="bold", ha="center", color=TEXT)
    ax.text(8, 10.15, "(Casos de uso del sistema con relaciones <<include>> y <<extend>>)",
            fontsize=10, ha="center", style="italic", color=GRAY)

    # Recuadro del sistema
    system_box = FancyBboxPatch((2.5, 0.8), 11, 8.7,
                                boxstyle="round,pad=0.08", linewidth=2,
                                edgecolor=BRAND, facecolor="#fbfdfb")
    ax.add_patch(system_box)
    ax.text(8, 9.2, "Sistema: Tienda Digital — Distrito Urbano",
            fontsize=11, fontweight="bold", color=BRAND, ha="center")

    # ---- Actores ----
    def actor(x, y, label, color=GRAY):
        # Cuerpo del stick figure
        ax.plot([x, x], [y, y - 0.45], color=color, linewidth=2)
        # Cabeza
        head = Circle((x, y + 0.12), 0.13, facecolor=color, edgecolor=color)
        ax.add_patch(head)
        # Brazos
        ax.plot([x - 0.28, x + 0.28], [y - 0.18, y - 0.18], color=color, linewidth=2)
        # Piernas
        ax.plot([x, x - 0.18], [y - 0.45, y - 0.85], color=color, linewidth=2)
        ax.plot([x, x + 0.18], [y - 0.45, y - 0.85], color=color, linewidth=2)
        # Label
        ax.text(x, y - 1.05, label, fontsize=9.5, ha="center", fontweight="bold", color=color)

    actor(1, 6.2, "Cliente", BRAND)
    actor(1, 3.5, "Administrador", "#7c3aed")
    actor(15, 6.2, "Pasarela\nde Pago", "#dc2626")
    actor(15, 3.5, "Sistema de\nCorreo (SMTP)", ACCENT)

    # ---- Casos de uso (elipses) ----
    def use_case(x, y, label, w=1.6, h=0.55, fill="white", edge=BRAND, fontsize=8.5):
        e = Ellipse((x, y), w, h, facecolor=fill, edgecolor=edge, linewidth=1.5)
        ax.add_patch(e)
        ax.text(x, y, label, fontsize=fontsize, ha="center", va="center",
                fontweight="bold", color=TEXT)

    # Casos de uso CLIENTE (lado izquierdo, arriba)
    use_case(4.5, 8.4, "Registrarse",         w=1.7)
    use_case(4.5, 7.5, "Iniciar sesión",      w=1.7)
    use_case(4.5, 6.5, "Explorar catálogo",   w=1.9)
    use_case(4.5, 5.5, "Buscar producto",     w=1.8)
    use_case(7.0, 6.5, "Consultar detalle\nde producto", w=2.0, h=0.7)
    use_case(7.5, 5.5, "Gestionar carrito",   w=1.9)
    use_case(7.5, 4.5, "Realizar checkout",   w=1.9)
    use_case(7.5, 3.5, "Procesar pago",       w=1.9, fill=ACCENT_LITE, edge=ACCENT)
    use_case(4.5, 4.5, "Ver mis pedidos",     w=1.9)
    use_case(4.5, 3.5, "Reseñar producto",    w=1.9)
    use_case(4.5, 2.5, "Recibir\nnotificación", w=1.9, h=0.7, fill=INFO_BG, edge="#2563eb")

    # Casos de uso ADMIN
    use_case(11.0, 8.4, "Gestionar catálogo\ne inventario", w=2.1, h=0.7)
    use_case(11.0, 7.3, "Gestionar pedidos\noperativos",    w=2.1, h=0.7)
    use_case(11.0, 6.2, "Aprobar reseñas",   w=1.9)
    use_case(11.0, 5.2, "Configurar tienda", w=1.9)
    use_case(11.0, 4.2, "Consultar\nfinanzas y reportes", w=2.1, h=0.7)
    use_case(11.0, 3.1, "Consultar bitácora\nde auditoría", w=2.1, h=0.7)
    use_case(11.0, 2.0, "Gestionar\nempleados/gastos", w=2.1, h=0.7,
             fill="#ede9fe", edge="#7c3aed")

    # ---- Líneas actor → casos de uso ----
    def link(x1, y1, x2, y2, color=GRAY, lw=1):
        ax.plot([x1, x2], [y1, y2], color=color, linewidth=lw, alpha=0.55)

    # Cliente
    for (xc, yc) in [(4.5, 8.4), (4.5, 7.5), (4.5, 6.5), (4.5, 5.5),
                      (7.5, 5.5), (7.5, 4.5), (4.5, 4.5), (4.5, 3.5),
                      (4.5, 2.5)]:
        link(1.25, 6.2, xc - 0.85, yc, BRAND, 1)

    # Admin
    for (xc, yc) in [(11.0, 8.4), (11.0, 7.3), (11.0, 6.2), (11.0, 5.2),
                      (11.0, 4.2), (11.0, 3.1), (11.0, 2.0)]:
        link(1.25, 3.5, xc - 1.05, yc, "#7c3aed", 1)

    # Admin también puede gestionar pedidos
    link(1.25, 3.5, 6.5, 4.5, "#7c3aed", 0.8)

    # Sistemas externos
    link(13.5, 5.5, 14.75, 6.2, "#dc2626", 1.2)  # Pasarela ← Procesar pago
    link(8.5, 3.5, 14.75, 6.2, "#dc2626", 1.0)
    link(5.5, 2.5, 14.75, 3.5, ACCENT, 1)        # SMTP ← Notificar

    # ---- Relaciones <<include>> y <<extend>> ----
    def include_arrow(x1, y1, x2, y2, label="<<include>>"):
        arr = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="->",
                              mutation_scale=14, color="#2563eb",
                              linestyle=(0, (5, 3)), linewidth=1.5)
        ax.add_patch(arr)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2 + 0.12
        ax.text(mx, my, label, fontsize=7, color="#2563eb",
                ha="center", style="italic", fontweight="bold")

    def extend_arrow(x1, y1, x2, y2, label="<<extend>>"):
        arr = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="->",
                              mutation_scale=14, color="#dc2626",
                              linestyle=(0, (5, 3)), linewidth=1.5)
        ax.add_patch(arr)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2 + 0.15
        ax.text(mx, my, label, fontsize=7, color="#dc2626",
                ha="center", style="italic", fontweight="bold")

    # Checkout <<include>> Procesar pago
    include_arrow(7.5, 4.22, 7.5, 3.78, "<<include>>")
    # Checkout <<include>> Gestionar carrito (depende del carrito)
    include_arrow(7.5, 5.22, 7.5, 4.78, "<<include>>")
    # Consultar detalle <<include>> Explorar catálogo (no, mejor extend al revés)
    # Buscar producto <<extend>> Explorar catálogo
    extend_arrow(4.5, 5.78, 4.5, 6.22, "<<extend>>")
    # Reseñar producto <<include>> Ver mis pedidos (necesitas un pedido entregado)
    include_arrow(4.5, 3.78, 4.5, 4.22, "<<include>>")
    # Procesar pago <<extend>> Recibir notificación (cuando se confirma)
    extend_arrow(6.55, 3.5, 5.45, 2.7, "<<extend>>")

    # Leyenda
    leg_x, leg_y = 0.4, 0.55
    legend_lines = [
        Line2D([0], [0], color=BRAND, lw=2, label="Asociación actor → caso de uso"),
        Line2D([0], [0], color="#2563eb", lw=2, ls="--", label="<<include>>  (caso obligatorio)"),
        Line2D([0], [0], color="#dc2626", lw=2, ls="--", label="<<extend>>  (caso opcional)"),
    ]
    ax.legend(handles=legend_lines, loc="lower center", ncol=3, frameon=True,
              fontsize=9, bbox_to_anchor=(0.5, -0.05))

    save(fig, "01_casos_de_uso")


# =============================================================================
# 2. DIAGRAMA DE SECUENCIA — CHECKOUT (SAGA orquestada síncrona)
# =============================================================================

def diagrama_secuencia_checkout():
    fig, ax = plt.subplots(figsize=(16, 12))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 12)
    ax.axis("off")

    ax.text(8, 11.5, "Diagrama de Secuencia — Realizar compra (Checkout SAGA)",
            fontsize=15, fontweight="bold", ha="center", color=TEXT)
    ax.text(8, 11.15, "Flujo orquestado: reservar inventario → cobrar → confirmar (o liberar)",
            fontsize=10, ha="center", style="italic", color=GRAY)

    # Lifelines (columnas verticales)
    actors = [
        ("Cliente",     1.4,  BRAND),
        ("Frontend\nReact",  3.6,  "#2563eb"),
        ("API Gateway",      5.8,  GRAY),
        ("Commerce\nService", 8.0,  BRAND),
        ("Inventory\nService",10.2, ACCENT),
        ("Payment\nService", 12.4, "#dc2626"),
        ("Pasarela\nMock",   14.6, "#7c3aed"),
    ]

    top = 10.5
    bot = 0.8

    for name, x, color in actors:
        # Caja del actor
        ax.add_patch(FancyBboxPatch((x - 0.7, top - 0.05), 1.4, 0.55,
                                     boxstyle="round,pad=0.04",
                                     facecolor=color, edgecolor=color))
        ax.text(x, top + 0.22, name, fontsize=8.5, ha="center", va="center",
                color="white", fontweight="bold")
        # Lifeline (línea punteada vertical)
        ax.plot([x, x], [top - 0.1, bot], color=color, linestyle=(0, (2, 3)),
                linewidth=1, alpha=0.6)

    # Función helper para mensajes
    def msg(y, x1, x2, label, color=TEXT, returned=False, dashed=False, hl=False):
        ls = "--" if (returned or dashed) else "-"
        arrow = "->>" if returned else "->"
        # flecha
        head = "->" if not returned else "->"
        ax.annotate("", xy=(x2, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle=head, color=color,
                                    lw=1.5, linestyle=ls))
        mx = (x1 + x2) / 2
        # fondo del texto para legibilidad
        ax.text(mx, y + 0.13, label, fontsize=8.0, ha="center", va="bottom",
                color=color, fontweight="bold" if hl else "normal",
                bbox=dict(facecolor="white", edgecolor="none", pad=1.5))

    def activation(x, ytop, ybot, color="white"):
        ax.add_patch(Rectangle((x - 0.09, ybot), 0.18, ytop - ybot,
                                facecolor=color, edgecolor=GRAY, linewidth=0.8))

    # Coords X
    XC, XF, XG, XCo, XI, XP, XM = 1.4, 3.6, 5.8, 8.0, 10.2, 12.4, 14.6

    # Flujo
    y = 9.8
    msg(y, XC, XF, "1. Confirmar pago en checkout"); y -= 0.4
    msg(y, XF, XG, "2. POST /api/checkout  +Idempotency-Key"); y -= 0.4
    msg(y, XG, XCo, "3. proxy_pass → commerce"); y -= 0.4

    # Activación Commerce
    activation(XCo, 9.5, 1.6, "#d4f0e1")

    msg(y, XCo, XCo, "4. Calcular totales del carrito", "#1f7a5c"); y -= 0.45
    msg(y, XCo, XI, "5. POST /reserve {items}", BRAND); y -= 0.4
    activation(XI, y + 0.6, y - 0.4, "#fed7aa")
    msg(y, XI, XI, "Lock distribuido Redis\n+ SELECT FOR UPDATE", ACCENT); y -= 0.55
    msg(y, XI, XCo, "201 reservation_ids", BRAND, returned=True); y -= 0.4

    msg(y, XCo, XP, "6. POST /payments {order_id, amount}", "#dc2626"); y -= 0.4
    activation(XP, y + 0.5, y - 1.0, "#fee2e2")
    msg(y, XP, XP, "Verifica Circuit Breaker", "#dc2626"); y -= 0.45
    msg(y, XP, XM, "POST /charge", "#7c3aed"); y -= 0.4
    msg(y, XM, XP, "200 APPROVED ref=AUTH-x", "#7c3aed", returned=True); y -= 0.4
    msg(y, XP, XCo, "200 {status: APPROVED}", "#dc2626", returned=True); y -= 0.45

    msg(y, XCo, XI, "7. POST /confirm/{order_id}", BRAND); y -= 0.4
    msg(y, XI, XI, "stock -= qty\nreserved_stock -= qty", ACCENT); y -= 0.55
    msg(y, XI, XCo, "200 OK", BRAND, returned=True); y -= 0.4

    msg(y, XCo, XCo, "8. Persistir Order(PAID) + OrderItems\n   + StatusHistory + AuditLog", "#1f7a5c", hl=True); y -= 0.65
    msg(y, XCo, XG, "9. 201 {order_id, status:PAID}", BRAND, returned=True); y -= 0.4
    msg(y, XG, XF, "10. proxy 201", GRAY, returned=True); y -= 0.4
    msg(y, XF, XC, "11. Mostrar pantalla ¡Pago aprobado!", "#2563eb", returned=True); y -= 0.4

    # Nota lateral (rama de error)
    ax.add_patch(FancyBboxPatch((6.0, 0.05), 8.5, 0.6,
                                 boxstyle="round,pad=0.08",
                                 facecolor="#fef3c7", edgecolor="#ca8a04", linewidth=1))
    ax.text(10.25, 0.35,
            "Flujo alternativo: si /payments responde REJECTED → Commerce llama /release a Inventory (compensación) y NO crea Order.\n"
            "Si CB está OPEN o pasarela cae → 503 inmediato; reserva liberada; cliente ve mensaje y carrito intacto.",
            fontsize=8, ha="center", va="center", color="#854d0e", fontstyle="italic")

    save(fig, "02_secuencia_checkout")


# =============================================================================
# 3. DIAGRAMA DE ACTIVIDAD — Flujo de compra del cliente (end-to-end)
# =============================================================================

def diagrama_actividad():
    fig, ax = plt.subplots(figsize=(11, 14))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 14)
    ax.axis("off")

    ax.text(5.5, 13.5, "Diagrama de Actividad — Proceso de compra del cliente",
            fontsize=14, fontweight="bold", ha="center", color=TEXT)

    def node(x, y, label, w=3.2, h=0.6, fill="white", edge=BRAND):
        ax.add_patch(FancyBboxPatch((x - w/2, y - h/2), w, h,
                                     boxstyle="round,pad=0.08",
                                     facecolor=fill, edgecolor=edge, linewidth=1.6))
        ax.text(x, y, label, fontsize=9, ha="center", va="center", color=TEXT,
                fontweight="bold")

    def start(x, y):
        ax.add_patch(Circle((x, y), 0.2, facecolor=BRAND, edgecolor=BRAND))

    def end(x, y):
        ax.add_patch(Circle((x, y), 0.2, facecolor="white", edgecolor=TEXT, linewidth=2))
        ax.add_patch(Circle((x, y), 0.12, facecolor=TEXT))

    def decision(x, y, label, size=0.45):
        diamond = Polygon([(x, y + size), (x + size * 1.3, y),
                            (x, y - size), (x - size * 1.3, y)],
                           facecolor=ACCENT_LITE, edgecolor=ACCENT, linewidth=1.6)
        ax.add_patch(diamond)
        ax.text(x, y, label, fontsize=8.5, ha="center", va="center",
                fontweight="bold", color="#854d0e")

    def arrow(x1, y1, x2, y2, label="", color=GRAY):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=color, lw=1.5))
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ax.text(mx + 0.18, my, label, fontsize=8, color=color,
                    fontweight="bold", style="italic",
                    bbox=dict(facecolor="white", edgecolor="none", pad=2))

    # Nodos
    start(5.5, 12.9)
    node(5.5, 12.2, "Iniciar sesión",                                w=3.0)
    node(5.5, 11.2, "Explorar catálogo / buscar producto",          w=4.5)
    node(5.5, 10.2, "Ver detalle y elegir variante\n(color + talla)", w=4.5, h=0.75)
    decision(5.5, 9.0, "¿Hay stock?")
    node(2.4, 9.0,  "Ver otro\nproducto", w=2.0, fill=GRAY_LITE)
    node(5.5, 7.8, "Agregar al carrito",                             w=3.0)
    node(5.5, 6.8, "Revisar carrito y\ncapturar datos de entrega",  w=4.5, h=0.7)
    node(5.5, 5.6, "Confirmar pago",                                 w=3.0)
    decision(5.5, 4.5, "¿SAGA OK?")
    node(2.0, 4.5,  "Mostrar error\n(stock / pago)", w=2.5, h=0.6, fill="#fee2e2", edge="#dc2626")
    node(5.5, 3.2,  "Crear Order(PAID)\n+ confirmar stock\n+ notificar al cliente",
         w=4.5, h=0.95, fill=BRAND_LITE)
    node(5.5, 1.7,  "Cliente recibe email + push y ve el pedido",   w=4.8, h=0.7)
    end(5.5, 0.6)

    # Flujos
    arrow(5.5, 12.7, 5.5, 12.5)
    arrow(5.5, 11.9, 5.5, 11.5)
    arrow(5.5, 10.9, 5.5, 10.55)
    arrow(5.5, 9.85, 5.5, 9.45)
    arrow(5.5, 8.55, 5.5, 8.1, "Sí")
    arrow(5.05, 9.0, 3.4, 9.0, "No")
    arrow(2.4, 8.7, 2.4, 11.5)
    arrow(2.4, 11.5, 3.25, 11.2)
    arrow(5.5, 7.5, 5.5, 7.15)
    arrow(5.5, 6.45, 5.5, 5.9)
    arrow(5.5, 5.3, 5.5, 4.95)
    arrow(5.5, 4.05, 5.5, 3.7, "Sí")
    arrow(5.05, 4.5, 3.25, 4.5, "No")
    arrow(2.0, 4.2, 2.0, 11.5)
    arrow(2.0, 11.5, 3.25, 11.2)
    arrow(5.5, 2.7, 5.5, 2.05)
    arrow(5.5, 1.35, 5.5, 0.8)

    save(fig, "03_actividad_compra")


# =============================================================================
# 4. DIAGRAMA DE ESTADO — Ciclo de vida del Pedido
# =============================================================================

def diagrama_estado_pedido():
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 9)
    ax.axis("off")

    ax.text(7, 8.5, "Diagrama de Estado — Ciclo de vida del Pedido",
            fontsize=15, fontweight="bold", ha="center", color=TEXT)
    ax.text(7, 8.15, "(Política MVP: la Order solo existe si el checkout llega a PAID)",
            fontsize=10, ha="center", style="italic", color=GRAY)

    def state(x, y, label, w=2.0, h=0.85, fill=BRAND_LITE, edge=BRAND, font=10):
        ax.add_patch(FancyBboxPatch((x - w/2, y - h/2), w, h,
                                     boxstyle="round,pad=0.08",
                                     facecolor=fill, edgecolor=edge, linewidth=2))
        ax.text(x, y, label, fontsize=font, ha="center", va="center",
                fontweight="bold", color=TEXT)

    def start(x, y):
        ax.add_patch(Circle((x, y), 0.18, facecolor=TEXT))

    def end(x, y):
        ax.add_patch(Circle((x, y), 0.22, facecolor="white", edgecolor=TEXT, linewidth=2))
        ax.add_patch(Circle((x, y), 0.11, facecolor=TEXT))

    def trans(x1, y1, x2, y2, label, color=GRAY, curve=0):
        if curve == 0:
            arr = FancyArrowPatch((x1, y1), (x2, y2),
                                   arrowstyle="->", mutation_scale=14,
                                   color=color, linewidth=1.6)
        else:
            arr = FancyArrowPatch((x1, y1), (x2, y2),
                                   arrowstyle="->", mutation_scale=14,
                                   color=color, linewidth=1.6,
                                   connectionstyle=f"arc3,rad={curve}")
        ax.add_patch(arr)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        if curve != 0:
            my += curve * 1.5
        ax.text(mx, my + 0.18, label, fontsize=8, ha="center",
                color=color, fontweight="bold", style="italic",
                bbox=dict(facecolor="white", edgecolor="none", pad=2))

    # Estado inicial
    start(1.0, 6.8)

    # Estados principales (flujo feliz)
    state(3.0, 6.8, "PAID", fill=BRAND_LITE, edge=BRAND)
    state(6.0, 6.8, "EN_PREPARACION", w=2.4, fill=INFO_BG, edge="#2563eb")
    state(9.5, 6.8, "ENVIADO", fill="#e0e7ff", edge="#4f46e5")
    state(12.5, 6.8, "ENTREGADO", fill=BRAND_LITE, edge=BRAND)

    # Estado final
    end(12.5, 4.0)

    # Estado terminal alternativo
    state(7.5, 4.0, "CANCELADA", w=2.0, fill="#fee2e2", edge="#dc2626")
    end(7.5, 1.8)

    # Transiciones (flujo feliz)
    trans(1.2, 6.8, 1.95, 6.8, "SAGA OK")
    trans(4.0, 6.8, 4.85, 6.8, "admin prepara")
    trans(7.2, 6.8, 8.5, 6.8, "admin despacha")
    trans(10.5, 6.8, 11.5, 6.8, "admin entrega")
    trans(12.5, 6.3, 12.5, 4.4, "fin")

    # Cancelaciones (desde PAID y EN_PREPARACION)
    trans(3.0, 6.35, 6.7, 4.4, "cancel.\nadmin", color="#dc2626", curve=-0.2)
    trans(6.0, 6.35, 7.5, 4.4, "cancel.\nadmin", color="#dc2626", curve=-0.15)
    trans(7.5, 3.6, 7.5, 2.2, "fin", color="#dc2626")

    # Recuadro "no-Order" — eventos que NO crean Order
    ax.add_patch(FancyBboxPatch((0.5, 0.25), 13, 1.2,
                                 boxstyle="round,pad=0.1",
                                 facecolor=WARN_BG, edgecolor="#ca8a04", linewidth=1.5))
    ax.text(7, 1.15, "Estados fallidos del checkout (NO crean Order — quedan en FailedCheckoutAttempt)",
            fontsize=10, ha="center", fontweight="bold", color="#854d0e")
    ax.text(7, 0.65,
            "out_of_stock  •  payment_rejected  •  payment_unavailable  •  inventory_unavailable  •  payment_pending/failed",
            fontsize=9, ha="center", color="#854d0e", style="italic")

    save(fig, "04_estado_pedido")


# =============================================================================
# 5. DIAGRAMA DE CLASES — Modelo de dominio (entidades principales)
# =============================================================================

def diagrama_clases():
    fig, ax = plt.subplots(figsize=(17, 13))
    ax.set_xlim(0, 17)
    ax.set_ylim(0, 13)
    ax.axis("off")

    ax.text(8.5, 12.6, "Diagrama de Clases — Modelo de dominio (entidades principales)",
            fontsize=15, fontweight="bold", ha="center", color=TEXT)
    ax.text(8.5, 12.25, "Agrupado por microservicio. Asociaciones cross-context son referencias lógicas (no FK física).",
            fontsize=10, ha="center", style="italic", color=GRAY)

    def klass(x, y, w, h, title, attrs, methods=None, bg="white", border=BRAND):
        # Caja principal
        ax.add_patch(Rectangle((x, y), w, h, facecolor=bg, edgecolor=border, linewidth=1.6))
        # Header
        ax.add_patch(Rectangle((x, y + h - 0.4), w, 0.4, facecolor=border, edgecolor=border))
        ax.text(x + w / 2, y + h - 0.2, title, fontsize=9.5, ha="center", va="center",
                fontweight="bold", color="white")
        # Atributos
        cur_y = y + h - 0.6
        for line in attrs:
            ax.text(x + 0.12, cur_y, line, fontsize=8, ha="left", va="top",
                    color=TEXT, family="monospace")
            cur_y -= 0.22
        # Separador
        if methods:
            sep_y = cur_y + 0.05
            ax.plot([x + 0.05, x + w - 0.05], [sep_y, sep_y], color=border, linewidth=0.8)
            cur_y -= 0.05
            for m in methods:
                ax.text(x + 0.12, cur_y, m, fontsize=8, ha="left", va="top",
                        color=TEXT, family="monospace", style="italic")
                cur_y -= 0.22

    # ========== Auth Service ==========
    ax.text(2.0, 11.7, "Auth Service", fontsize=11, fontweight="bold", color="#0891b2")
    klass(0.4, 9.0, 3.1, 2.5, "User",
          ["- id: int", "- email: str <<unique>>",
           "- password_hash: str", "- name: str",
           "- phone: str", "- role: str  (customer|admin)",
           "- created_at: datetime"],
          bg="#cffafe", border="#0891b2")
    klass(0.4, 6.5, 3.1, 2.2, "RefreshToken",
          ["- id: int", "- user_id: int (FK)",
           "- token_hash: str", "- expires_at: datetime",
           "- revoked: bool"],
          bg="#ecfeff", border="#0891b2")
    klass(0.4, 4.0, 3.1, 2.2, "AccessLog",
          ["- id: int", "- user_id: int (FK, nullable)",
           "- action: str (login|register|...)", "- ip: str",
           "- user_agent: str", "- correlation_id: str",
           "- created_at: datetime"],
          bg="#ecfeff", border="#0891b2")

    # ========== Catalog Service ==========
    ax.text(5.4, 11.7, "Catalog Service", fontsize=11, fontweight="bold", color=BRAND)
    klass(4.0, 9.5, 3.1, 2.0, "Category",
          ["- id: int", "- name: str", "- description: str",
           "- active: bool", "- archived: bool"],
          bg=BRAND_LITE, border=BRAND)
    klass(4.0, 7.0, 3.1, 2.3, "Product",
          ["- id: int", "- category_id: int (FK)",
           "- name: str", "- description: str",
           "- long_description: text",
           "- base_price: decimal", "- image_url: str",
           "- published: bool", "- archived: bool"],
          bg=BRAND_LITE, border=BRAND)
    klass(4.0, 4.5, 3.1, 2.2, "ProductImage",
          ["- id: int", "- product_id: int (FK)",
           "- image_url: str", "- alt_text: str"],
          bg="#ecfdf5", border=BRAND)
    klass(4.0, 2.0, 3.1, 2.2, "RatingSummary",
          ["- product_id: int (PK)",
           "- average: float", "- count: int",
           "- updated_at: datetime"],
          bg="#ecfdf5", border=BRAND)

    # ========== Inventory Service ==========
    ax.text(8.7, 11.7, "Inventory Service", fontsize=11, fontweight="bold", color=ACCENT)
    klass(7.3, 9.0, 3.1, 2.5, "ProductVariant",
          ["- id: int",
           "- product_id: int  <<ref-logica>>",
           "- sku: str <<unique>>",
           "- color: str  /  color_hex: str",
           "- size: str",
           "- cost: decimal / price: decimal",
           "- stock: int / reserved_stock: int",
           "- active: bool"],
          bg=ACCENT_LITE, border=ACCENT)
    klass(7.3, 6.5, 3.1, 2.2, "StockReservation",
          ["- id: int", "- variant_id: int (FK)",
           "- order_id: str  <<ref-logica>>",
           "- quantity: int",
           "- status: PENDING|CONFIRMED|RELEASED",
           "- expires_at: datetime"],
          bg="#fff7ed", border=ACCENT)
    klass(7.3, 4.0, 3.1, 2.2, "StockMovement",
          ["- id: int", "- variant_id: int (FK)",
           "- movement_type: str",
           "- quantity: int", "- reason: str",
           "- user_id: int", "- order_id: str",
           "- correlation_id: str"],
          bg="#fff7ed", border=ACCENT)
    klass(7.3, 1.5, 3.1, 2.2, "LowStockAlert",
          ["- id: int", "- variant_id: int (FK)",
           "- threshold: int",
           "- stock_at_alert: int",
           "- resolved: bool"],
          bg="#fff7ed", border=ACCENT)

    # ========== Commerce Service ==========
    ax.text(12.1, 11.7, "Commerce Service", fontsize=11, fontweight="bold", color="#2563eb")
    klass(10.6, 9.5, 3.2, 2.0, "Cart",
          ["- id: int",
           "- user_id: int <<ref-logica>>",
           "- status: open|checked_out"],
          bg=INFO_BG, border="#2563eb")
    klass(10.6, 7.0, 3.2, 2.3, "CartItem",
          ["- id: int", "- cart_id: int (FK)",
           "- variant_id: int <<ref-logica>>",
           "- product_id: int <<ref-logica>>",
           "- product_name: str (snapshot)",
           "- quantity: int", "- unit_price: decimal"],
          bg="#eff6ff", border="#2563eb")
    klass(10.6, 4.0, 3.2, 2.8, "Order",
          ["- id: int", "- order_code: str <<unique>>",
           "- user_id: int <<ref-logica>>",
           "- status: PAID|EN_PREP|ENVIADO|ENTREGADO|CANCEL",
           "- payment_status: APPROVED|...",
           "- subtotal/total: decimal",
           "- delivery_*: str  (snapshot)",
           "- correlation_id: str"],
          bg=INFO_BG, border="#2563eb")
    klass(10.6, 1.0, 3.2, 2.8, "OrderItem",
          ["- id: int", "- order_id: int (FK)",
           "- variant_id: int <<ref-logica>>",
           "- product_id: int <<ref-logica>>",
           "- product_name: str (snapshot)",
           "- quantity: int",
           "- unit_price: decimal",
           "- unit_cost: decimal (snapshot)",
           "- total: decimal"],
          bg="#eff6ff", border="#2563eb")

    klass(14.0, 9.5, 2.8, 2.0, "Review",
          ["- id: int", "- product_id: int",
           "- order_id: int (FK)",
           "- user_id: int", "- rating: 1..5",
           "- comment: str", "- approved: bool"],
          bg="#fef3c7", border="#ca8a04")
    klass(14.0, 7.0, 2.8, 2.3, "Notification",
          ["- id: int", "- user_id: int",
           "- order_id: int (FK, nullable)",
           "- title/message: str",
           "- read: bool", "- read_at: datetime"],
          bg="#fef9c3", border="#ca8a04")
    klass(14.0, 4.0, 2.8, 2.8, "OrderAuditLog",
          ["- id: int",
           "- order_id: int (FK, nullable)",
           "- action: str",
           "- performed_by: int",
           "- details: text",
           "- correlation_id: str"],
          bg="#fef9c3", border="#ca8a04")
    klass(14.0, 1.0, 2.8, 2.8, "FailedCheckoutAttempt",
          ["- id: int",
           "- user_id: int",
           "- attempt_code: str",
           "- reason_code: str",
           "- message/subtotal",
           "- correlation_id: str",
           "- payload: text"],
          bg="#fef3c7", border="#ca8a04")

    klass(14.0, -1.5, 2.8, 2.2, "Employee, Expense",
          ["(soporte financiero)",
           "- Employee: salary, status",
           "- Expense: amount, date,",
           "  type, observation"],
          bg="#f3e8ff", border="#7c3aed")

    # ========== Payment Service ==========
    ax.text(0.4, 1.4, "Payment Service (DB propia)", fontsize=10,
            fontweight="bold", color="#dc2626")
    klass(0.4, 0.0, 3.1, 1.3, "Payment",
          ["- id, order_id, amount, currency",
           "- status: APPROVED|REJECTED|...",
           "- transaction_reference, payment_id",
           "- created_at"],
          bg="#fee2e2", border="#dc2626")

    # ====== Relaciones internas (mismas DB) ======
    def assoc(x1, y1, x2, y2, label="", color=GRAY, ls="-", lw=1.3):
        ax.plot([x1, x2], [y1, y2], color=color, linewidth=lw, linestyle=ls)
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ax.text(mx, my, label, fontsize=7, color=color, fontweight="bold",
                    bbox=dict(facecolor="white", edgecolor="none", pad=1))

    # Auth
    assoc(2.0, 9.0, 2.0, 8.7, "1..*", "#0891b2")
    assoc(2.0, 6.5, 2.0, 6.2, "1..*", "#0891b2")
    # Catalog
    assoc(5.55, 9.5, 5.55, 9.3, "1..*", BRAND)
    assoc(5.55, 7.0, 5.55, 6.7, "1..*", BRAND)
    assoc(5.55, 7.0, 5.55, 4.2, "1..1", BRAND)
    # Inventory
    assoc(8.85, 9.0, 8.85, 8.7, "1..*", ACCENT)
    assoc(8.85, 9.0, 8.85, 6.2, "1..*", ACCENT)
    assoc(8.85, 9.0, 8.85, 3.7, "1..*", ACCENT)
    # Commerce
    assoc(12.2, 9.5, 12.2, 9.3, "1..*", "#2563eb")
    assoc(12.2, 4.0, 12.2, 3.8, "1..*", "#2563eb")

    # Cross-context (refs lógicas) — punteadas
    assoc(7.1, 8.0, 10.6, 7.0, "ref", "#777", "--")
    assoc(7.1, 5.5, 10.6, 1.5, "ref", "#777", "--")
    assoc(10.4, 9.7, 3.5, 9.7, "ref user_id", "#777", "--")
    assoc(0.4, 1.0, 14.0, 1.0, "ref order_code/id", "#777", "--", lw=0.8)

    # Leyenda
    leg = [
        mpatches.Patch(color="#0891b2", label="Auth Service"),
        mpatches.Patch(color=BRAND, label="Catalog Service"),
        mpatches.Patch(color=ACCENT, label="Inventory Service"),
        mpatches.Patch(color="#2563eb", label="Commerce Service"),
        mpatches.Patch(color="#ca8a04", label="Commerce / Audit / Notif."),
        mpatches.Patch(color="#dc2626", label="Payment Service"),
        Line2D([0], [0], color="#777", lw=1.5, ls="--", label="Referencia lógica cross-context"),
    ]
    ax.legend(handles=leg, loc="upper left", bbox_to_anchor=(0.0, -0.02),
              ncol=4, frameon=True, fontsize=8.5)

    save(fig, "05_clases_dominio")


# =============================================================================
# 6. DIAGRAMA DE COMPONENTES — Arquitectura de microservicios
# =============================================================================

def diagrama_componentes():
    fig, ax = plt.subplots(figsize=(18, 13))
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 13)
    ax.axis("off")

    ax.text(9, 12.5, "Diagrama de Componentes — Arquitectura de microservicios",
            fontsize=16, fontweight="bold", ha="center", color=TEXT)

    def component(x, y, w, h, name, sub="", bg="white", border=BRAND):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                                     boxstyle="round,pad=0.06",
                                     facecolor=bg, edgecolor=border, linewidth=1.8))
        # Icono UML de componente
        ax.add_patch(Rectangle((x + w - 0.55, y + h - 0.4), 0.4, 0.3,
                                facecolor="white", edgecolor=border, linewidth=1))
        ax.add_patch(Rectangle((x + w - 0.65, y + h - 0.35), 0.18, 0.1,
                                facecolor="white", edgecolor=border, linewidth=1))
        ax.add_patch(Rectangle((x + w - 0.65, y + h - 0.20), 0.18, 0.1,
                                facecolor="white", edgecolor=border, linewidth=1))
        ax.text(x + w / 2 - 0.3, y + h - 0.30, name, fontsize=10.5, ha="center",
                fontweight="bold", color=TEXT)
        if sub:
            ax.text(x + w / 2, y + 0.35, sub, fontsize=8.2, ha="center",
                    style="italic", color=GRAY)

    def db(x, y, label, color="#94a3b8"):
        ax.add_patch(Ellipse((x, y + 0.7), 1.3, 0.22, facecolor=color, edgecolor=color))
        ax.add_patch(Rectangle((x - 0.65, y + 0.1), 1.3, 0.6, facecolor=color, edgecolor=color))
        ax.add_patch(Ellipse((x, y + 0.1), 1.3, 0.22, facecolor=color, edgecolor=color))
        ax.text(x, y + 0.4, label, fontsize=8.5, ha="center", va="center",
                fontweight="bold", color="white")

    def arrow(x1, y1, x2, y2, label="", color=GRAY, ls="-", offset=0.12):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color=color, lw=1.5, linestyle=ls))
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            ax.text(mx, my + offset, label, fontsize=8, ha="center",
                    color=color, fontweight="bold",
                    bbox=dict(facecolor="white", edgecolor="none", pad=2))

    # ---------- Capa 1: Cliente + Gateway ----------
    component(1.5, 10.6, 3.3, 1.4, "Frontend SPA",
              "React + Vite\n(puerto 5173)", bg=INFO_BG, border="#2563eb")
    component(7.0, 10.6, 4.0, 1.4, "API Gateway",
              "Nginx (puerto 80)\nRouting · CORS · Rate-limit · Correlation-id",
              bg="#f1f5f9", border=GRAY)

    # Flecha Frontend → Gateway
    arrow(4.8, 11.3, 7.0, 11.3, "HTTPS / JSON + JWT", "#2563eb")

    # ---------- Capa 2: 5 microservicios ----------
    SVC_Y = 7.2
    SVC_H = 1.7
    component(0.5, SVC_Y, 3.0, SVC_H, "Auth Service",
              "FastAPI :8001\nJWT HS256\nRegistro · login\nrefresh · bitácora",
              bg="#cffafe", border="#0891b2")
    component(4.0, SVC_Y, 3.0, SVC_H, "Catalog Service",
              "FastAPI :8002\nProductos · categorías\nmensajes · settings\nCache-Aside Redis",
              bg=BRAND_LITE, border=BRAND)
    component(7.5, SVC_Y, 3.0, SVC_H, "Inventory Service",
              "FastAPI :8003\nVariantes · stock\nreservas · alertas\nLock distribuido",
              bg=ACCENT_LITE, border=ACCENT)
    component(11.0, SVC_Y, 3.0, SVC_H, "Commerce Service",
              "FastAPI :8004\nCarrito · SAGA\npedidos · reseñas\nfinanzas · audit",
              bg=INFO_BG, border="#2563eb")
    component(14.5, SVC_Y, 3.0, SVC_H, "Payment Service",
              "FastAPI :8005\nCircuit Breaker\nRetries exponenciales\nReconciler async",
              bg="#fee2e2", border="#dc2626")

    # Flechas Gateway → microservicios (rutas)
    routes = [
        (9, 10.6, 2.0, 8.9, "/api/auth", "#0891b2"),
        (9, 10.6, 5.5, 8.9, "/api/products\n/api/catalog", BRAND),
        (9, 10.6, 9.0, 8.9, "/api/inventory", ACCENT),
        (9, 10.6, 12.5, 8.9, "/api/cart\n/api/checkout", "#2563eb"),
        (9, 10.6, 16.0, 8.9, "/api/payments", "#dc2626"),
    ]
    for x1, y1, x2, y2, lbl, col in routes:
        arrow(x1, y1, x2, y2, lbl, col, offset=0.0)

    # ---------- Capa 3: Bases de datos (MySQL multi-schema) ----------
    # Marco MySQL
    ax.add_patch(FancyBboxPatch((0.3, 4.0), 17.4, 1.8,
                                 boxstyle="round,pad=0.08",
                                 facecolor="#fffbeb", edgecolor=GRAY,
                                 linewidth=1.4, linestyle=(0, (4, 3))))
    ax.text(9, 5.6, "MySQL 8.4   (multi-schema · Database per Service)",
            fontsize=10, ha="center", color=GRAY, fontweight="bold", style="italic")

    db(2.0,  4.2, "auth_db",      "#0891b2")
    db(5.5,  4.2, "catalog_db",   BRAND)
    db(9.0,  4.2, "inventory_db", ACCENT)
    db(12.5, 4.2, "commerce_db",  "#2563eb")
    db(16.0, 4.2, "payments_db",  "#dc2626")

    # Servicio → su DB
    for (xs, col) in [(2.0, "#0891b2"), (5.5, BRAND), (9.0, ACCENT),
                       (12.5, "#2563eb"), (16.0, "#dc2626")]:
        arrow(xs, SVC_Y, xs, 5.0, "", col)

    # ---------- Capa 4: Infraestructura adicional ----------
    INF_Y = 1.2
    component(0.5,  INF_Y, 3.0, 1.5, "Redis 7",
              "Cache-Aside\nLocks distribuidos\nCB state",
              bg="#fee2e2", border="#dc2626")
    component(4.0,  INF_Y, 3.0, 1.5, "Mailhog",
              "SMTP local\nUI :8025",
              bg="#fef3c7", border="#ca8a04")
    component(7.5,  INF_Y, 3.0, 1.5, "Payment Mock",
              "Pasarela simulada\n4 escenarios:\nAPPROVED/REJECTED\nPENDING/FAILED",
              bg="#f3e8ff", border="#7c3aed")
    component(11.0, INF_Y, 3.0, 1.5, "phpMyAdmin",
              "UI inspección DB\n(puerto 8080)",
              bg="#f1f5f9", border=GRAY)

    # Conexiones a infraestructura (líneas más sutiles)
    # Catalog/Inventory/Payment → Redis
    arrow(5.5, SVC_Y, 1.8, INF_Y + 1.5, "cache", "#dc2626", ls=":", offset=-0.05)
    arrow(9.0, SVC_Y, 1.8, INF_Y + 1.5, "lock", "#dc2626", ls=":", offset=-0.05)
    arrow(16.0, SVC_Y, 1.8, INF_Y + 1.5, "CB", "#dc2626", ls=":", offset=-0.05)

    # Auth/Commerce → Mailhog
    arrow(2.0, SVC_Y, 5.3, INF_Y + 1.5, "welcome", "#ca8a04", ls=":")
    arrow(12.5, SVC_Y, 5.3, INF_Y + 1.5, "order emails", "#ca8a04", ls=":")

    # Payment → Mock
    arrow(16.0, SVC_Y, 9.0, INF_Y + 1.5, "charge", "#7c3aed", ls=":")

    # SAGA entre microservicios (líneas REST horizontales sobre la capa de servicios)
    ax.text(9, 9.6, "  Comunicación REST entre microservicios (orquestada por Commerce)",
            fontsize=8, ha="center", color="#7c3aed", style="italic",
            bbox=dict(facecolor="white", edgecolor="#7c3aed", boxstyle="round,pad=0.3"))
    # Commerce → Inventory (reserve/confirm/release)
    arrow(11.0, 7.8, 10.5, 7.8, "reserve/confirm/release", "#7c3aed", ls="--", offset=0.1)
    # Commerce → Payment (charge)
    arrow(14.0, 7.6, 14.5, 7.6, "charge", "#7c3aed", ls="--", offset=0.1)
    # Catalog → Inventory (stock-summary, variants)
    arrow(7.0, 7.8, 7.5, 7.8, "stock-summary/variants", "#7c3aed", ls="--", offset=0.1)
    # Commerce → Catalog (rating update)
    arrow(11.0, 7.6, 7.0, 7.6, "rating update", "#7c3aed", ls="--", offset=-0.18)

    save(fig, "06_componentes")


# =============================================================================
# 7. DIAGRAMA DE DESPLIEGUE — nodos físicos / contenedores Docker
# =============================================================================

def diagrama_despliegue():
    fig, ax = plt.subplots(figsize=(18, 12))
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 12)
    ax.axis("off")

    ax.text(9, 11.5, "Diagrama de Despliegue — Contenedores Docker (entorno local)",
            fontsize=16, fontweight="bold", ha="center", color=TEXT)
    ax.text(9, 11.1, "12 contenedores en una red Docker bridge (tienda_net)",
            fontsize=10, ha="center", style="italic", color=GRAY)

    def container(x, y, w, h, name, port, color="white", border=BRAND, image=""):
        ax.add_patch(FancyBboxPatch((x, y), w, h,
                                     boxstyle="round,pad=0.05",
                                     facecolor=color, edgecolor=border, linewidth=1.7))
        ax.text(x + w / 2, y + h - 0.22, name, fontsize=9.5, ha="center",
                fontweight="bold", color=TEXT)
        if image:
            ax.text(x + w / 2, y + h - 0.50, image, fontsize=7.5, ha="center",
                    color=GRAY, style="italic")
        ax.text(x + w / 2, y + 0.18, port, fontsize=8, ha="center",
                color=GRAY, family="monospace")

    # ---------- Nodo host ----------
    ax.add_patch(FancyBboxPatch((0.3, 0.4), 17.4, 10.0,
                                 boxstyle="round,pad=0.1",
                                 facecolor="#f8fafc", edgecolor=TEXT, linewidth=1.5))
    ax.text(0.6, 10.1, "<<device>> Equipo del estudiante",
            fontsize=9, color=GRAY, style="italic")
    ax.text(0.6, 9.8, "Windows + Docker Desktop",
            fontsize=11, fontweight="bold", color=TEXT)

    # ---------- Subred Docker ----------
    ax.add_patch(FancyBboxPatch((0.8, 1.2), 16.4, 7.6,
                                 boxstyle="round,pad=0.1",
                                 facecolor="white", edgecolor=GRAY,
                                 linewidth=1.5, linestyle=(0, (5, 4))))
    ax.text(9, 8.5, "<<network>> tienda_net   (Docker bridge)",
            fontsize=10, ha="center", style="italic", color=GRAY,
            bbox=dict(facecolor="white", edgecolor="none", pad=2))

    # ---------- Capa Gateway ----------
    container(1.3, 6.8, 2.6, 1.2, "tienda_gateway",
              "80 → 80", color="#f1f5f9", border=GRAY,
              image="image: nginx:alpine")

    # ---------- Capa Microservicios ----------
    SVC_Y = 6.8
    SVC_H = 1.2
    container(4.6,  SVC_Y, 2.2, SVC_H, "tienda_auth",
              "8001 → 8001", color="#cffafe", border="#0891b2",
              image="build: ./services/auth-service")
    container(7.1,  SVC_Y, 2.2, SVC_H, "tienda_catalog",
              "8002 → 8002", color=BRAND_LITE, border=BRAND,
              image="build: catalog-service")
    container(9.6,  SVC_Y, 2.2, SVC_H, "tienda_inventory",
              "8003 → 8003", color=ACCENT_LITE, border=ACCENT,
              image="build: inventory-service")
    container(12.1, SVC_Y, 2.2, SVC_H, "tienda_commerce",
              "8004 → 8004", color=INFO_BG, border="#2563eb",
              image="build: commerce-service")
    container(14.6, SVC_Y, 2.2, SVC_H, "tienda_payment",
              "8005 → 8005", color="#fee2e2", border="#dc2626",
              image="build: payment-service")

    # ---------- Capa Infraestructura ----------
    INF_Y = 4.7
    container(1.3,  INF_Y, 2.6, 1.2, "tienda_digital_mysql",
              "3306 → 3306", color="#fef3c7", border="#ca8a04",
              image="image: mysql:8.4")
    container(4.1,  INF_Y, 2.2, 1.2, "tienda_redis",
              "6379 → 6379", color="#fee2e2", border="#dc2626",
              image="image: redis:7-alpine")
    container(6.5,  INF_Y, 2.2, 1.2, "tienda_mailhog",
              "1025 + 8025", color="#fef3c7", border="#ca8a04",
              image="image: mailhog/mailhog")
    container(8.9,  INF_Y, 2.2, 1.2, "tienda_phpmyadmin",
              "8080 → 80", color="#f1f5f9", border=GRAY,
              image="image: phpmyadmin")
    container(11.3, INF_Y, 2.2, 1.2, "tienda_payment_mock",
              "9000 → 9000", color="#f3e8ff", border="#7c3aed",
              image="build: ./payment-mock")
    container(13.7, INF_Y, 3.0, 1.2, "volumes: mysql_data",
              "named volumes", color="#ede9fe", border="#7c3aed",
              image="+ ./database, ./database-init")

    # ---------- Conexiones internas ----------
    def conn(x1, y1, x2, y2, color=GRAY, ls=":"):
        ax.plot([x1, x2], [y1, y2], color=color, linewidth=1, alpha=0.5, linestyle=ls)

    # Gateway → cada microservicio (mismo nivel)
    for x in [5.7, 8.2, 10.7, 13.2, 15.7]:
        conn(3.9, 7.4, x - 1.1, 7.4, GRAY, "-")
        ax.plot([3.9, 4.0], [7.4, 7.4], color=GRAY, lw=1.2)

    # Microservicios → MySQL
    for x in [5.7, 8.2, 10.7, 13.2, 15.7]:
        conn(x, 6.8, 2.6, 5.9, "#ca8a04", "-")

    # Servicios → Redis (Catalog, Inventory, Payment)
    for x in [8.2, 10.7, 15.7]:
        conn(x, 6.8, 5.2, 5.9, "#dc2626", ":")

    # Auth y Commerce → Mailhog
    for x in [5.7, 13.2]:
        conn(x, 6.8, 7.6, 5.9, "#ca8a04", ":")

    # Payment → Mock
    conn(15.7, 6.8, 12.4, 5.9, "#7c3aed", ":")

    # ---------- Cliente externo (fuera de la subred Docker) ----------
    container(1.3, 2.0, 7.0, 1.0,
              "Frontend dev server  (npm run dev)",
              "5173 (host del estudiante)",
              color="#f0fdf4", border=BRAND,
              image="React + Vite — fuera de Docker, accede via http://localhost")
    container(9.0, 2.0, 7.5, 1.0,
              "Cliente / Admin (navegador)",
              "→ http://localhost  (puerto 80 del gateway)",
              color="#fff7ed", border=ACCENT,
              image="Chrome / Firefox / Safari")

    # Flecha de cliente → gateway
    ax.annotate("", xy=(2.6, 6.8), xytext=(4.8, 3.0),
                arrowprops=dict(arrowstyle="->", color=ACCENT, lw=1.6, linestyle="--"))
    ax.text(3.3, 4.7, "HTTPS\nJSON", fontsize=8, color=ACCENT,
            fontweight="bold", style="italic",
            bbox=dict(facecolor="white", edgecolor="none", pad=2))

    # ---------- Nota ----------
    ax.text(9, 1.0,
            "Healthchecks: cada microservicio expone GET /health en su puerto interno.\n"
            "El gateway re-expone GET /health/<svc> en el puerto 80 (Doctor Monkey).",
            fontsize=8.5, ha="center", color=GRAY, style="italic",
            bbox=dict(facecolor="#fef3c7", edgecolor="#ca8a04", boxstyle="round,pad=0.4"))

    save(fig, "07_despliegue")


if __name__ == "__main__":
    print("Generando diagramas UML...")
    diagrama_casos_uso()
    diagrama_secuencia_checkout()
    diagrama_actividad()
    diagrama_estado_pedido()
    diagrama_clases()
    diagrama_componentes()
    diagrama_despliegue()
    print(f"\nDiagramas generados en {OUT}")
