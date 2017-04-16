from .util import message
import discord
import cah
import time
import math
import random

DEBUG = True

MIN_PLAYERS = 2


class SeverGame(cah.Game):
    def __init__(self, client, channel_id, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.client = client
        self.channel_id = channel_id

        self.on_message = self.client.event(self.on_message)

        self.tzar_select_mode = False

    def dereg_on_message(self):
        delattr(self.client, self.on_message.__name__)

    async def ask_and_wait(self):
        match_join_message = ("It's time to play some CAH!" +
                              " React to this message, if you would like to play.")

        msg = await self.client.send_message(discord.Object(id=self.channel_id), match_join_message)

        wait_update_del = 5
        wait_amt = 20
        wait_start = time.time()
        old_wait_left = None
        while True:
            wait_left = wait_amt - (time.time() - wait_start)
            if not old_wait_left == math.floor(wait_left / wait_update_del):
                old_wait_left = math.floor(wait_left / wait_update_del)
                msg = await self.client.edit_message(msg, new_content=match_join_message + " T-" + str(math.ceil(wait_left)))
            time.sleep(0.5)

            if wait_left <= 0:
                break

        return msg

    async def send_player_cards(self):
        self.deal_cards()

        for p in self.players:
            if p == self.card_tzar:
                continue
            u = p.id

            msg = "```\n"
            for i, c in enumerate(p.cards):
                msg += str(i) + ". " + str(p.cards[c]) + "\n"
            msg += "```"
            await self.client.send_message(u, content=msg)

    @staticmethod
    def get_if_authors_channel(msg):
        try:
            if not msg.author == msg.channel.user:
                return False
        except AttributeError:
            return False
        return True

    async def get_choice_from_message(self, msg):
        content = msg.content.strip(" ").strip("\n")

        try:
            choice = int(content)
        except ValueError:
            # Was not integer, warn player:
            await self.client.send_message(msg.channel, "Please try again.")
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

        # Exit if the author is this client or not a player:
        if author == self.client.user or not any(x.id == author for x in self.players):
            return

        # Get content of the message and strip un-needed characters
        content = msg.content.strip(" ").strip("\n")

        # Get first player in list with the message author object as its id:
        ply = [x for x in self.players if x.id == msg.author][0]

        # Exit if the player has already selected a card:
        if ply in self.player_cards:
            return

        # Attempt conversion of the message content to an integer:
        choice = await self.get_choice_from_message(msg)
        if choice is None:
            return

        # Get card_content and card_id:
        card_id = list(ply.cards.keys())[choice]
        card_content = ply.select_card(card_id)

        # Tell user what card was selected:
        await self.client.send_message(msg.channel, "You selected {}: {} ({})".format(choice, card_content, card_id))

        # Add card to player_cards dict:
        self.player_cards[ply] = card_content

        ply_test_arr = self.players[:]
        del(ply_test_arr[ply_test_arr.index(self.card_tzar)])
        if all(x in ply_test_arr for x in list(self.player_cards.keys())):
            print("EVERYONE")
            await self.start_tzar_select_mode()
            self.tzar_select_mode = True

        print(self.player_cards)

    async def start_tzar_select_mode(self):
        list_cards = "Question: `{}`".format(self.curr_question[1])
        list_cards += "\n Choose one card: ```"
        for i, ck in enumerate(self.player_cards.keys()):
            list_cards += "{}: {}".format(i, self.player_cards[ck])
        list_cards += "\n```"
        await self.client.send_message(self.card_tzar.id, list_cards)
        pass

    async def tzar_select_message(self, msg):
        if self.get_if_authors_channel(msg) is False:
            return

        # Check that user is tzar:
        if not msg.author == self.card_tzar.id:
            return

        choice = await self.get_choice_from_message(msg)
        if choice is None:
            return

        plyr = list(self.player_cards.keys())[choice]
        crd = list(self.player_cards.items())[choice]

        del(self.player_cards[plyr])

        plyr.add_win(crd, plyr, self.player_cards)

        self.player_cards = {}

        await self.client.send_message(discord.Object(id=self.channel_id), "Winner: `{}`.".format(crd[1]))

        await self.start_round()

    async def on_message(self, msg):
        if not self.tzar_select_mode:
            await self.card_selection_message(msg)
        else:
            await self.tzar_select_message(msg)

    async def start_round(self):
        self.tzar_select_mode = False

        self.get_new_question()

        question_msg = "The Question is: `{}`".format(self.curr_question[1])
        await self.client.send_message(discord.Object(id=self.channel_id), question_msg)

        self.card_tzar = random.choice(self.players)

        await self.send_player_cards()

        '''
        start_time = time.time()
        wait_time = 30  # seconds

        while (time.time()-start_time)<wait_time and all(x in self.players for x in list(self.player_cards.keys())):
            print("wait")
            time.sleep(0.2)'''
        print("finish")

    async def run(self):
        # Wait for client ready:
        await self.client.wait_until_ready()

        # Send initial game message:
        init_msg = await self.ask_and_wait()

        users_player = await message.get_react_users(self.client, init_msg)
        for p in users_player:
            self.add_player_id(p)

        num_plyr = len(self.players)
        if num_plyr < MIN_PLAYERS:
            await self.client.send_message(discord.Object(id=self.channel_id),
                                           "Not enough players ({} < {}).".format(num_plyr, MIN_PLAYERS))
            return

        await self.start_round()
