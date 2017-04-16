async def get_react_users(client, msg):
    usrs = []

    for r in msg.reactions:
        us = await client.get_reaction_users(r)
        for u in us:
            if u not in usrs:
                usrs.append(u)

    return usrs
