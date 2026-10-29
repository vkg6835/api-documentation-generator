from flask import Flask, Blueprint, request, abort

app = Flask(__name__)
tickets = Blueprint("tickets", __name__, url_prefix="/tickets")
TICKETS = {}


@tickets.route("", methods=["GET"])
def list_tickets():
    """List all tickets held in this demonstration process."""
    return {"tickets": list(TICKETS.values())}


@tickets.route("", methods=["POST"])
def create_ticket():
    """Create a support ticket from the supplied JSON title."""
    data = request.get_json()
    ticket_id = len(TICKETS) + 1
    ticket = {"id": ticket_id, "title": data["title"], "status": "open"}
    TICKETS[ticket_id] = ticket
    return ticket, 201


@tickets.get("/<int:ticket_id>")
def get_ticket(ticket_id):
    """Return one support ticket or report that it is missing."""
    if ticket_id not in TICKETS:
        abort(404)
    return TICKETS[ticket_id]


@tickets.patch("/<int:ticket_id>/close")
def close_ticket(ticket_id):
    """Mark an existing ticket as closed."""
    if ticket_id not in TICKETS:
        abort(404)
    TICKETS[ticket_id]["status"] = "closed"
    return TICKETS[ticket_id]


app.register_blueprint(tickets, url_prefix="/api/tickets")
