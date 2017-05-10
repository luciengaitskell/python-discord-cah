from .util import message
import discord
import cah
import time
import math
import random
import asyncio

DEBUG = True

MIN_PLAYERS = 2


class SeverGame(cah.Game):
    new_round_message = ".\n\n----------------NEW ROUND----------------"
    player_chose_message_content_initial = "Here's who has submitted so far:```"

    def __init__(self, client, channel_id, game_end_callback=None, reg_msg_method=True, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.client = client
        self.channel_id = channel_id
        self.game_end_callback = game_end_callback

        self.alive = True

        if reg_msg_method:
            self.on_message = self.client.event(self.on_message)

        self.tzar_select_mode = False

        self.player_chose_message = None
        self.player_chose_message_content = None

        self.round_messages = []

    async def end(self):
        self.alive = False
        await self.end_round()
        await self.game_end_callback(self)

    def dereg_on_message(self):
        delattr(self.client, self.on_message.__name__)

    async def message_all_players(self, msg_content):
        for p in self.players:
            await self.send_message(p.id, msg_content)

    async def send_message(self, *args, **kwargs):
        msg = await self.client.send_message(*args, **kwargs)
        self.round_messages.append(msg)
        return msg

    async def ask_and_wait(self):
        match_join_message = ("It's time to play some CAH!" +
                              " React to this message, if you would like to play.")

        msg = await self.send_message(discord.Object(id=self.channel_id), match_join_message)

        wait_update_del = 5
        wait_amt = 20
        wait_start = time.time()
        old_wait_left = None
        while True:
            wait_left = wait_amt - (time.time() - wait_start)

            if not self.alive:
                await self.client.edit_message(msg, new_content=match_join_message + " [CANCELED]")
                break

            # Triggers if the time block has changed (each are "wait_update_del" in size)
            #   so the timer should be updated:
            if not old_wait_left == math.floor(wait_left / wait_update_del):
                # Update the current time block:
                old_wait_left = math.floor(wait_left / wait_update_del)
                msg = await self.client.edit_message(msg, new_content=match_join_message + " T-" + str(math.ceil(wait_left)))

            if wait_left <= 0:
                break

            await asyncio.sleep(wait_update_del)

        return msg

    async def send_player_cards(self):
        self.deal_cards()

        for p in self.players:
            u = p.id

            if p == self.card_tzar:
                msg = "You are the card tzar. Please wait until all players choose their cards."
            else:
                msg = "```\n"
                for i, c in enumerate(p.cards):
                    msg += str(i) + ". " + str(p.cards[c]) + "\n"
                msg += "```"
            await self.send_message(u, content=msg)

    @staticmethod
    def get_if_authors_channel(msg):
        try:
            if not msg.author == msg.channel.user:
                return False
        except AttributeError:
            return False
        return True

    async def get_choice_from_message(self, msg):
        # Get content of the message and strip un-needed characters
        content = msg.content.strip(" ").strip("\n")

        try:
            choice = int(content)
        except ValueError:
            # Was not integer, warn player:
            await self.send_message(msg.channel, "Please try again.")
            return None
        return choice

    async def card_selection_message(self, msg):
        # Get author of message:
        author = msg.author

        # Message debug prints:
        if DEBUG:
            print(author)
            print(type(author))
            print(self.client.user)
            print(type(author))

        # Check if the message is from the authors's channel (PM):
        if self.get_if_authors_channel(msg) is False:
                return

        # Exit if the author is this client or not a player or is card tzar:
        if author == self.client.user or not any(x.id == author for x in self.players)\
                or msg.author == self.card_tzar.id:
            return

        # Get first player in list with the message author object as its id:
        ply = [x for x in self.players if x.id == msg.author][0]

        # Exit if the player has already selected a card:
        if ply in self.player_cards:
            return

        # Attempt conversion of the message content to an integer:
        choice = await self.get_choice_from_message(msg)
        if choice is None:
            return

        try:
            # Get card_content and card_id:
            card_id = list(ply.cards.keys())[choice]
        except IndexError:
            await self.send_message(msg.channel, "Out of range. Please try again.")
            return

        card_content = ply.select_card(card_id)

        # Tell user what card was selected:
        await self.send_message(msg.channel, "You selected {}: {} ({})".format(choice, card_content, card_id))

        # Add card to player_cards dict:
        self.player_cards[ply] = card_content

        self.player_chose_message_content += "\n" + author.name
        try:
            await self.client.edit_message(self.player_chose_message, new_content=self.player_chose_message_content + "```")
        except discord.errors.NotFound:
            print("Error updating player list message.")

        print(self.player_cards)

    async def start_tzar_select_mode(self):
        are_cards = False
        # Notify of tzar mode
        await self.message_all_players("Now awaiting tzar card selection.")

        list_cards = "\n Choose one card: ```"
        for i, ck in enumerate(self.player_cards.keys()):
            are_cards = True
            list_cards += "\n{}: {}".format(i, self.player_cards[ck])
        list_cards += "\n```"

        if not are_cards:
            await self.message_all_players("No cards were submitted!")
            await self.start_round()
        else:
            await self.send_message(self.card_tzar.id, list_cards)

    async def tzar_select_message(self, msg):
        if self.get_if_authors_channel(msg) is False:
            return

        # Check that user is tzar:
        if not msg.author == self.card_tzar.id:
            return

        choice = await self.get_choice_from_message(msg)
        if choice is None:
            return

        try:
            plyr = list(self.player_cards.keys())[choice]
        except IndexError:
            await self.send_message(msg.channel, "Out of range. Please try again.")
            return

        crd = self.player_cards[plyr]

        del(self.player_cards[plyr])

        plyr.add_win(crd, plyr, self.player_cards)

        self.player_cards = {}

        await self.message_all_players("Winner '{}': `{}`.".format(plyr.id.name, crd))

        await asyncio.sleep(5)
        await self.end_round()
        await self.start_round()

    async def on_message(self, msg):
        if not self.tzar_select_mode:
            await self.card_selection_message(msg)
        else:
            await self.tzar_select_message(msg)

    async def end_round(self):
        print("END")
        for msg in self.round_messages:
            self.client.loop.create_task(self.client.delete_message(msg))
        self.round_messages = []

    async def start_round(self):
        self.player_cards = {}
        self.tzar_select_mode = False

        self.get_new_question()

        self.card_tzar = random.choice(self.players)

        # Send new round message content
        await self.send_message(discord.Object(id=self.channel_id), self.new_round_message)
        await self.message_all_players(self.new_round_message)

        initial_msg = "'{}' is the card tzar.\n".format(self.card_tzar.id.name)
        initial_msg += "The Question is: `{}`".format(self.curr_question[1])
        await self.message_all_players(initial_msg)

        self.player_chose_message_content = self.player_chose_message_content_initial
        self.player_chose_message = await self.send_message(discord.Object(id=self.channel_id),
                                                            self.player_chose_message_content + "\nNone...```")

        await self.send_player_cards()

        start_time = time.time()
        wait_time = 30  # seconds

        ply_test_arr = self.players[:]
        del (ply_test_arr[ply_test_arr.index(self.card_tzar)])
        while ((time.time()-start_time) < wait_time and
                not all(x in list(self.player_cards.keys()) for x in ply_test_arr) and self.alive):
            print("wait")
            await asyncio.sleep(2)

        if len(self.player_cards) == 0:
            await self.message_all_players("No cards were submitted! Leaving.")
            await self.end()
            return

        print("EVERYONE")
        await self.start_tzar_select_mode()
        self.tzar_select_mode = True
        print("finish")

    async def run(self):
        # Wait for client ready:
        await self.client.wait_until_ready()

        # Send initial game message:
        init_msg = await self.ask_and_wait()

        if not self.alive:
            return

        users_player = await message.get_react_users(self.client, init_msg)
        for p in users_player:
            self.add_player_id(p)

        num_plyr = len(self.players)
        if num_plyr < MIN_PLAYERS:
            await self.send_message(discord.Object(id=self.channel_id),
                                    "Not enough players ({} < {}).".format(num_plyr, MIN_PLAYERS))
            await self.end()
            return

        await self.start_round()

    @classmethod
    def create_session(cls, client, invoke_msg, game_end_callback=None):
        """Create game session from a channel."""
        channel = invoke_msg.channel

        if type(channel) == discord.channel.PrivateChannel:
            client.send_message(invoke_msg.channel, "I'm afraid you can't start a fantastical game by yourself. Sorry.")
        else:
            g = cls(client, invoke_msg.channel.id, game_end_callback, reg_msg_method=False)
        client.loop.create_task(g.run())
        return g
